import os
import json
import asyncio
from services.supabase_service import _get_supabase
from services.AI_extract_service import get_llm
from langchain_core.messages import HumanMessage, SystemMessage
from core.config import settings
from langchain_google_genai import ChatGoogleGenerativeAI

# Paths to the local markdown files in the frontend component
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
TRANSCRIPT_PATH = os.path.join(FRONTEND_DIR, "src", "app", "meeting-room", "transcript.md")
WALKTHROUGH_PATH = os.path.join(FRONTEND_DIR, "src", "app", "meeting-room", "interview-walkthrough.md")

# Active interview sessions keyed by user_interview_id
# Each session stores: questions, current_index, queue, user_name, track_title
active_sessions = {}

# In-memory fallback storage for transcript/walkthrough on ephemeral filesystems (e.g. Render)
_in_memory_transcripts = {}  # keyed by user_interview_id
_in_memory_walkthroughs = {}  # keyed by user_interview_id

DEFAULT_TRANSCRIPT = "# Interview Transcript\n\n"
DEFAULT_WALKTHROUGH = "# Interview Walkthrough\n\n"


def _get_transcript(session_id: str) -> str:
    return _in_memory_transcripts.get(session_id, DEFAULT_TRANSCRIPT)


def _get_walkthrough(session_id: str) -> str:
    return _in_memory_walkthroughs.get(session_id, DEFAULT_WALKTHROUGH)


def read_file_content(file_path: str) -> str:
    """Read contents of a file if it exists, falling back to in-memory storage."""
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
    # Fallback to default for ephemeral filesystems
    if file_path == TRANSCRIPT_PATH:
        return DEFAULT_TRANSCRIPT
    elif file_path == WALKTHROUGH_PATH:
        return DEFAULT_WALKTHROUGH
    return ""


def reset_interview_files(session_id: str):
    """Clear or initialize transcript and walkthrough for a session."""
    _in_memory_transcripts[session_id] = DEFAULT_TRANSCRIPT
    _in_memory_walkthroughs[session_id] = DEFAULT_WALKTHROUGH
    os.makedirs(os.path.dirname(TRANSCRIPT_PATH), exist_ok=True)
    try:
        with open(TRANSCRIPT_PATH, "w", encoding="utf-8") as f:
            f.write(DEFAULT_TRANSCRIPT)
        with open(WALKTHROUGH_PATH, "w", encoding="utf-8") as f:
            f.write(DEFAULT_WALKTHROUGH)
        print("Initialized transcript.md and interview-walkthrough.md")
    except Exception as e:
        print(f"Error initializing files (best-effort on ephemeral FS): {e}")


def append_to_transcript(session_id: str, speaker: str, text: str):
    """Append a dialogue turn to transcript."""
    entry = f"**{speaker}**: {text}\n\n"
    _in_memory_transcripts[session_id] = _in_memory_transcripts.get(session_id, DEFAULT_TRANSCRIPT) + entry
    try:
        with open(TRANSCRIPT_PATH, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        print(f"Error appending to transcript.md (in-memory fallback active): {e}")


def append_to_walkthrough(session_id: str, question_text: str, category: str, difficulty: str, response: str, diagram_url: str = None):
    """Append question and candidate answer details to walkthrough."""
    entry = f"### Question: {question_text}\n"
    entry += f"* **Category**: {category.capitalize()}\n"
    entry += f"* **Difficulty**: {difficulty.capitalize()}\n\n"
    entry += f"**User Response**:\n{response}\n\n"
    if diagram_url:
        entry += f"**Candidate Diagram**:\n![Candidate Diagram]({diagram_url})\n\n"
    entry += "---\n\n"
    _in_memory_walkthroughs[session_id] = _in_memory_walkthroughs.get(session_id, DEFAULT_WALKTHROUGH) + entry
    try:
        with open(WALKTHROUGH_PATH, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        print(f"Error appending to interview-walkthrough.md (in-memory fallback active): {e}")


def send_to_client(session_id: str, message: dict):
    """Push a message to the client via the session's asyncio queue."""
    session = active_sessions.get(session_id)
    if session and "queue" in session:
        try:
            session["queue"].put_nowait(message)
        except asyncio.QueueFull:
            print(f"WARNING: Message queue full for session {session_id}, dropping message")
    else:
        print(f"WARNING: No active session/queue for {session_id}")


def get_or_create_session_queue(session_id: str) -> asyncio.Queue:
    """Get or create the message queue for a session."""
    if session_id not in active_sessions:
        active_sessions[session_id] = {"queue": asyncio.Queue(maxsize=100)}
    elif "queue" not in active_sessions[session_id]:
        active_sessions[session_id]["queue"] = asyncio.Queue(maxsize=100)
    return active_sessions[session_id]["queue"]


async def get_interview_questions(user_interview_id: str):
    """Load questions list from supabase for a user_interview_id with transient error retry logic."""
    loop = asyncio.get_event_loop()

    def _fetch():
        supabase = _get_supabase()

        # 1. Fetch user_interview record
        res_ui = supabase.table("user_interview").select("*").eq("id", user_interview_id).single().execute()
        user_interview = res_ui.data
        if not user_interview:
            raise ValueError(f"User interview record with ID {user_interview_id} not found")

        interview_id = user_interview.get("interview_id")

        # 2. Fetch ai-interview record
        res_ai = supabase.table("ai-interview").select("*").eq("id", interview_id).single().execute()
        ai_interview = res_ai.data
        if not ai_interview:
            raise ValueError(f"AI interview track with ID {interview_id} not found")

        return ai_interview.get("interview_question", [])

    for attempt in range(3):
        try:
            return await loop.run_in_executor(None, _fetch)
        except Exception as e:
            if attempt == 2:
                raise e
            print(f"Fetch questions failed (attempt {attempt + 1}/3): {e}. Retrying in 1s...")
            await asyncio.sleep(1)


async def polish_user_response(raw_text: str) -> str:
    """Polishes raw transcribed user speech using Gemma-4-31B."""
    if not raw_text.strip():
        return "No response provided."

    llm = get_llm()
    system_msg = SystemMessage(
        content="You are a text-polishing AI. The user is transcribing their voice response in a live interview. "
                "Your job is to fix any spelling mistakes, grammar errors, and remove verbal filler words (e.g., 'um', 'uh', 'like', 'ah', 'so', 'you know', 'basically') to make it a polished, professional sentence. "
                "Keep the candidate's core meaning and context completely intact. Do NOT add any introductory text, explanations, or comments. Return ONLY the polished response text."
    )
    human_msg = HumanMessage(content=raw_text)
    try:
        res = await llm.ainvoke([system_msg, human_msg])
        return res.content.strip()
    except Exception as e:
        print(f"Error polishing response with Gemma: {e}")
        return raw_text


async def generate_ai_reply(question_text: str, user_response: str) -> str:
    """Generates real-time professional reply / follow-up to user response using Gemma-4-31B."""
    llm = get_llm()
    system_msg = SystemMessage(
        content="You are a supportive and professional AI interviewer. "
                "Acknowledge the candidate's response to the current question in a warm, constructive, and concise manner (1-2 sentences). "
                "You may highlight a strong point they made or provide brief encouraging feedback. "
                "Keep your reply under 3 sentences total, and make it direct so it can be spoken out loud via text-to-speech."
    )
    human_msg = HumanMessage(
        content=f"Question asked: {question_text}\nCandidate response: {user_response}"
    )
    try:
        res = await llm.ainvoke([system_msg, human_msg])
        return res.content.strip()
    except Exception as e:
        print(f"Error generating AI reply: {e}")
        return "Thank you for sharing that answer. Let's move on to the next question."


async def process_user_answer(user_interview_id: str, raw_text: str, diagram_url: str = None):
    """Processes user response, polishes it, updates files, calls LLM, and sends next question."""
    session = active_sessions.get(user_interview_id)
    if not session:
        print(f"No active session for {user_interview_id}")
        return

    questions = session["questions"]
    idx = session["current_index"]
    current_q = questions[idx]

    # Send status to frontend
    send_to_client(user_interview_id, {"type": "status", "message": "Polishing response..."})

    # 1. Polish user response using Gemma-4-31B
    polished_text = await polish_user_response(raw_text)

    # 2. Append to transcript and walkthrough files
    append_to_transcript(user_interview_id, "Candidate", polished_text)
    if diagram_url:
        append_to_transcript(user_interview_id, "Candidate (Diagram)", f"![Diagram]({diagram_url})")
    append_to_walkthrough(user_interview_id, current_q["question_text"], current_q.get("type", "technical"), current_q.get("difficulty", "medium"), polished_text, diagram_url)

    # Send status to frontend
    send_to_client(user_interview_id, {"type": "status", "message": "Formulating feedback..."})

    # 3. Call Gemma-4-31B for realtime reply/feedback
    ai_reply = await generate_ai_reply(current_q["question_text"], polished_text)

    # 4. Append AI reply to transcript
    append_to_transcript(user_interview_id, "Interviewer", ai_reply)

    # 5. Determine next question
    next_idx = idx + 1
    session["current_index"] = next_idx

    next_q = None
    if next_idx < len(questions):
        next_q = questions[next_idx]
        # Append next question to transcript on disk
        append_to_transcript(user_interview_id, "Interviewer", f"Let's move to the next question. {next_q['question_text']}")

        # Read updated files to send to frontend
        updated_transcript = _get_transcript(user_interview_id)
        updated_walkthrough = _get_walkthrough(user_interview_id)

        # Send response back to the client
        response_payload = {
            "type": "ai_reply",
            "text": ai_reply,
            "next_question": next_q["question_text"],
            "next_index": next_idx,
            "transcript": updated_transcript,
            "walkthrough": updated_walkthrough,
            "interview_completed": False,
            "diagram_tool": next_q.get("diagram_tool", False)
        }
        send_to_client(user_interview_id, response_payload)
    else:
        # Append final ending to transcript
        completion_msg = "This concludes our interview. Thank you for your time. I will now generate your comprehensive evaluation report. Please wait."
        append_to_transcript(user_interview_id, "Interviewer", completion_msg)

        # Read updated files to send to frontend
        updated_transcript = _get_transcript(user_interview_id)
        updated_walkthrough = _get_walkthrough(user_interview_id)

        # Send response back to the client indicating completion
        response_payload = {
            "type": "ai_reply",
            "text": ai_reply,
            "next_question": None,
            "next_index": next_idx,
            "transcript": updated_transcript,
            "walkthrough": updated_walkthrough,
            "interview_completed": True
        }
        send_to_client(user_interview_id, response_payload)

        # Launch report generation task using gemini-2.5-flash
        asyncio.create_task(generate_and_upload_report(
            user_interview_id=user_interview_id,
            user_name=session.get("user_name", "Candidate"),
            track_title=session.get("track_title", "General Practice Interview")
        ))


async def generate_and_upload_report(user_interview_id: str, user_name: str, track_title: str):
    """Generates a performance evaluation report using Gemini 2.5 Flash, uploads to Supabase storage, and updates DB."""
    try:
        send_to_client(user_interview_id, {"type": "status", "message": "Analyzing performance & generating evaluation report..."})

        # 1. Fetch transcript and walkthrough content
        transcript_content = _get_transcript(user_interview_id)
        walkthrough_content = _get_walkthrough(user_interview_id)

        # 2. Invoke Gemini 2.5 Flash
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            temperature=0.2,
            google_api_key=settings.GEMINI_API_KEY
        )

        system_msg = SystemMessage(
            content="You are an expert Executive Interview Coach and Technical Recruiter. "
                    "Analyze the provided transcript and walkthrough of the interview, and generate a beautiful, "
                    "comprehensive performance evaluation report in Markdown. "
                    "Include sections for Executive Summary, Strengths, Improvement Areas (with concrete examples), "
                    "and a final Grade / Compatibility Score (out of 100%). "
                    "Ensure the markdown structure is neat, clean, and highly readable. "
                    "Do NOT wrap the output in ```markdown code blocks. Return ONLY the raw markdown text."
        )

        human_msg = HumanMessage(
            content=f"Candidate Name: {user_name}\n"
                    f"Interview Role / Track: {track_title}\n\n"
                    f"--- INTERVIEW TRANSCRIPT ---\n{transcript_content}\n\n"
                    f"--- DETAILED Q&A WALKTHROUGH ---\n{walkthrough_content}"
        )

        print(f"Calling gemini-2.5-flash for interview report of {user_name}...")
        response = await llm.ainvoke([system_msg, human_msg])
        report_markdown = response.content.strip()

        # 3. Fetch user session database data (auth_id, interview_id)
        supabase = _get_supabase()
        res_ui = supabase.table("user_interview").select("auth_id, interview_id").eq("id", user_interview_id).single().execute()
        ui_data = res_ui.data
        if not ui_data:
            raise ValueError("User interview session record not found")

        auth_id = ui_data.get("auth_id")
        interview_id = ui_data.get("interview_id")

        # 4. Upload report to 'ai-interview' storage bucket
        file_path = f"{auth_id}/{interview_id}.md"
        report_bytes = report_markdown.encode("utf-8")

        print(f"Uploading report to Supabase bucket 'ai-interview' path: {file_path}...")
        try:
            supabase.storage.from_("ai-interview").upload(
                path=file_path,
                file=report_bytes,
                file_options={"content-type": "text/markdown", "upsert": "true"}
            )
        except Exception as e:
            # Fallback to update if row exists or RLS upload policy requires it
            print(f"Upload failed, performing fallback update: {e}")
            supabase.storage.from_("ai-interview").update(
                path=file_path,
                file=report_bytes,
                file_options={"content-type": "text/markdown"}
            )

        # 5. Get public URL of the uploaded file
        report_url = supabase.storage.from_("ai-interview").get_public_url(file_path)
        print(f"Uploaded report. URL: {report_url}")

        # 6. Update database record: report_url and interview_completed = True
        supabase.table("user_interview").update({
            "report_url": [report_url],
            "interview_completed": True
        }).eq("id", user_interview_id).execute()

        # 7. Notify client that report is ready
        send_to_client(user_interview_id, {
            "type": "report_ready",
            "report_url": report_url
        })

    except Exception as e:
        print(f"Error generating and uploading report: {e}")
        send_to_client(user_interview_id, {
            "type": "error",
            "message": f"Failed to generate performance report: {str(e)}"
        })


async def start_session(user_interview_id: str):
    """Resets files, loads questions, and sends the first question to the user."""
    try:
        # 1. Reset files
        reset_interview_files(user_interview_id)

        # Ensure queue exists
        get_or_create_session_queue(user_interview_id)

        # 2. Fetch questions from supabase
        send_to_client(user_interview_id, {"type": "status", "message": "Loading questions..."})
        questions = await get_interview_questions(user_interview_id)

        if not questions:
            send_to_client(user_interview_id, {"type": "error", "message": "No questions found for this interview track."})
            return

        # Get track title and candidate full name from database with retries
        track_title = "General Practice Interview"
        user_name = "Candidate"
        loop = asyncio.get_event_loop()

        def _fetch_metadata():
            supabase = _get_supabase()
            res_ui = supabase.table("user_interview").select("interview_id, auth_id").eq("id", user_interview_id).single().execute()
            if not res_ui.data:
                return None
            auth_id = res_ui.data.get("auth_id")
            int_id = res_ui.data.get("interview_id")

            res_track = supabase.table("ai-interview").select("title").eq("id", int_id).single().execute()
            track_title_val = res_track.data.get("title") if res_track.data else "General Practice Interview"

            res_user = supabase.table("user_data").select("data").eq("user_id", auth_id).single().execute()
            user_name_val = "Candidate"
            if res_user.data and "data" in res_user.data:
                user_name_val = res_user.data["data"].get("full_name", "Candidate")
            return track_title_val, user_name_val

        for attempt in range(3):
            try:
                metadata = await loop.run_in_executor(None, _fetch_metadata)
                if metadata:
                    track_title, user_name = metadata
                break
            except Exception as e:
                print(f"Fetch metadata failed (attempt {attempt + 1}/3): {e}. Retrying in 1s...")
                if attempt == 2:
                    print("Error fetching metadata for starting session, falling back to defaults")
                await asyncio.sleep(1)

        # Initialize session state (preserve existing queue)
        existing_queue = active_sessions.get(user_interview_id, {}).get("queue")
        active_sessions[user_interview_id] = {
            "user_interview_id": user_interview_id,
            "questions": questions,
            "current_index": 0,
            "queue": existing_queue or asyncio.Queue(maxsize=100),
            "user_name": user_name,
            "track_title": track_title
        }

        # 3. Format and send first question
        first_q = questions[0]
        greeting = "Hello! Welcome to your simulated practice interview. Let's start with the first question."

        append_to_transcript(user_interview_id, "Interviewer", f"{greeting} {first_q['question_text']}")

        updated_transcript = _get_transcript(user_interview_id)
        updated_walkthrough = _get_walkthrough(user_interview_id)

        send_to_client(user_interview_id, {
            "type": "first_question",
            "greeting": greeting,
            "question": first_q["question_text"],
            "index": 0,
            "transcript": updated_transcript,
            "walkthrough": updated_walkthrough,
            "diagram_tool": first_q.get("diagram_tool", False)
        })

    except Exception as e:
        print(f"Error starting session: {e}")
        send_to_client(user_interview_id, {"type": "error", "message": f"Failed to start session: {str(e)}"})


def cleanup_session(user_interview_id: str):
    """Remove session data when interview ends or client disconnects."""
    if user_interview_id in active_sessions:
        del active_sessions[user_interview_id]
    if user_interview_id in _in_memory_transcripts:
        del _in_memory_transcripts[user_interview_id]
    if user_interview_id in _in_memory_walkthroughs:
        del _in_memory_walkthroughs[user_interview_id]
    print(f"Cleaned up session for {user_interview_id}")
