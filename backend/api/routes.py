from typing import List
from typing import Any
from typing import Dict
from pydantic import BaseModel
import uuid
from fastapi import Form
import asyncio

import pycountry
from aiolimiter import AsyncLimiter

from services.AI_extract_service import AIOrganiser
from services.supabase_service import store_data, retrieve_data, clear_all_user_data
from services.job_fetcher import fetch_job_list
from services.job_parser import fast_rank_jobs, normalise_job_record
from core.config import settings

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from core.security import get_supabase_client
from supabase import Client

from services.pinecone_service import embed_job_data, organise_user_data

router = APIRouter()

# define limit and concurrency
# 15 RPM = 1 request every 4 seconds. Use 4.5s for safety margin.
# max_rate=1 means exactly 1 token available at a time (no burst).
rate_limiter = AsyncLimiter(max_rate=1, time_period=4.5)
sem = asyncio.Semaphore(1)  # Strictly serialize all Gemma calls

class RemapJobsRequest(BaseModel):
    user_data_dict: Dict[str, Any]
    organised_job_result: List[Dict[str, Any]]

@router.post("/search-initial-jobs")
async def search_initial_jobs(country: str = Form(...),
                            state: str | None = Form(default=None),
                            is_intern: bool = Form(default=False),
                            expected_salary: int | None = Form(default=None, ge=0),
                            search_query: str | None = Form(default=None),
                            file: UploadFile | None = File(default=None),
                            supabase: Client = Depends(get_supabase_client)):

    uid = supabase.user.id

    if file is None and not (search_query and search_query.strip()):
        raise HTTPException(status_code=400, detail="Must upload resume pdf or enter search query")

    # Validate country BEFORE clearing data
    country_obj = pycountry.countries.get(name=country)
    if not country_obj:
        raise HTTPException(status_code=400, detail=f"Invalid country name")
    country_abbr = country_obj.alpha_2.lower()

    # Validate file type BEFORE clearing data
    if file is not None:
        if file.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Valid Resume PDF file required")

    # Clear previous search data from database to prevent stale data
    await clear_all_user_data(uid, supabase_client=supabase)

    auto_match_enabled = False
    user_data_dict = None

    if file is not None:
    
        # Analyze Resume
        async with rate_limiter:
            async with sem:
                resume_result = await AIOrganiser.resume_analysis(file)
        if not resume_result.is_valid_resume:
            raise HTTPException(status_code=400, detail="Invalid PDF file")

        # prepare job search info. If the user also types a keyword, prioritise it
        # as a search override/refinement while keeping resume-inferred roles.
        job_search_info = list(resume_result.target_job_roles or [])
        if search_query and search_query.strip():
            job_search_info.insert(0, search_query.strip())
        auto_match_enabled = True

    else:
        job_search_info = [search_query.strip()]

    # Fetch and fast-parse real jobs from SerpAPI. No demo/mock jobs are generated.
    raw_job_result = await fetch_job_list(job_search_info, country, country_abbr, state, is_intern)

    # Prepare user data to send back and persist (only exists if a resume was uploaded)
    if file is not None:
        user_data_dict = resume_result.model_dump()
        if expected_salary is not None:
            user_data_dict["expected_salary"] = expected_salary

    # Production persistence guarantee:
    # Save the SerpAPI extraction immediately, before returning to the frontend.
    # This prevents data loss if the browser closes before the ReMAP call finishes.
    if raw_job_result:
        await store_data(raw_job_result, "job_data", uid, supabase_client=supabase)

    if user_data_dict:
        await store_data(user_data_dict, "user_data", uid, supabase_client=supabase)

    
    return {
        "uid": uid,
        "user_data_dict": user_data_dict,
        "raw_job_result": raw_job_result,
        "auto_match_enabled": auto_match_enabled,
        "saved_to_supabase": True,
        "saved_job_count": len(raw_job_result)
    }

class SingleJobExtractRequest(BaseModel):
    raw_job: Dict[str, Any]

@router.post("/extract-single-job")
async def extract_single_job(payload: SingleJobExtractRequest, supabase: Client = Depends(get_supabase_client)):
    """Fast compatibility endpoint.

    The old implementation made one serial LLM call per job, which was the main
    reason searches could take many minutes. SerpAPI already provides structured
    job_highlights/detected_extensions, so the normal path now uses the local
    parser and returns in milliseconds.
    """
    return normalise_job_record(payload.raw_job, payload.raw_job.get("target_job_role"))

@router.post("/remap-and-sort-jobs")
async def remap_n_sort_jobs(payload: RemapJobsRequest, supabase: Client = Depends(get_supabase_client)):
    uid = supabase.user.id
    user_data_dict = payload.user_data_dict
    organised_job_result = [
        normalise_job_record(job, job.get("target_job_role"))
        for job in (payload.organised_job_result or [])
        if isinstance(job, dict)
    ]

    if not organised_job_result:
        return {"jobs": [], "remap_applied": False}

    if not user_data_dict:
        print("No user data provided. Skipping ReMAP and returning parsed jobs.")
        try:
            await asyncio.gather(
                store_data(organised_job_result, "job_data", uid, supabase_client=supabase),
                store_data(organised_job_result, "final_job_data", uid, supabase_client=supabase),
            )
        except Exception as e:
            print(f"WARNING: Error storing job data without resume: {e}")
        return {"jobs": organised_job_result, "remap_applied": False}

    # 1) Always produce a fast deterministic ranking first. This fixes the old
    # failure mode where Pinecone or per-job LLM calls could return 0 jobs or 500.
    final_ordered_job = fast_rank_jobs(user_data_dict, organised_job_result)

    # 2) Best-effort persistence and vector indexing. These should not block the
    # user from receiving recommendations.
    async def _safe_call(label: str, coro):
        try:
            return await coro
        except Exception as e:
            print(f"WARNING: {label} failed but fast matching will continue: {e}")
            return None

    pinecone_timeout = max(5, int(getattr(settings, "PINECONE_TIMEOUT_SECONDS", 20) or 20))

    await asyncio.gather(
        _safe_call("store job_data", store_data(organised_job_result, "job_data", uid, supabase_client=supabase)),
        _safe_call("store user_data", store_data(user_data_dict, "user_data", uid, supabase_client=supabase)),
        _safe_call("embed job_data", asyncio.wait_for(embed_job_data(final_ordered_job, uid), timeout=pinecone_timeout)),
    )

    # 3) Optional Pinecone reorder. Use it only as a tie-breaker/semantic boost,
    # never as a hard dependency.
    try:
        ordered_job_ids = await asyncio.wait_for(
            asyncio.to_thread(organise_user_data, user_data_dict, uid),
            timeout=pinecone_timeout,
        )
        if ordered_job_ids:
            job_by_id = {job.get("job_id"): job for job in final_ordered_job if job.get("job_id")}
            pinecone_rank = {job_id: idx for idx, job_id in enumerate(ordered_job_ids)}
            for job in final_ordered_job:
                if job.get("job_id") in pinecone_rank:
                    job["pinecone_rank"] = pinecone_rank[job.get("job_id")] + 1
                    job["logical_match_score"] = min(100, int(job.get("logical_match_score", 0)) + 3)
                    job["matching_method"] = "fast_local_remap_plus_pinecone"
            final_ordered_job.sort(
                key=lambda x: (x.get("logical_match_score", 0), -int(x.get("pinecone_rank", 9999))),
                reverse=True,
            )
    except Exception as e:
        print(f"WARNING: Pinecone ranking failed; using fast local ranking only: {e}")

    # 4) Optional LLM refinement for only the top N jobs. Default is 0 to keep the
    # production path inside the 1-3 minute target.
    top_n_for_llm = max(0, int(getattr(settings, "FAST_MATCH_TOP_N_FOR_LLM", 0) or 0))
    if top_n_for_llm > 0:
        refined_jobs = []
        for job in final_ordered_job[:top_n_for_llm]:
            try:
                async with rate_limiter:
                    async with sem:
                        refined = await asyncio.wait_for(AIOrganiser.job_remap(user_data_dict, job), timeout=35.0)
                        if refined:
                            refined["matching_method"] = "llm_refined_remap"
                            refined_jobs.append(refined)
                            continue
            except Exception as e:
                print(f"WARNING: Optional LLM remap skipped for {job.get('job_id')}: {e}")
            refined_jobs.append(job)
        final_ordered_job = refined_jobs + final_ordered_job[top_n_for_llm:]
        final_ordered_job.sort(key=lambda x: x.get("logical_match_score", 0), reverse=True)

    await _safe_call("store final_job_data", store_data(final_ordered_job, "final_job_data", uid, supabase_client=supabase))

    print("Successfully executed optimized analyse_and_match_job")
    return {"jobs": final_ordered_job, "remap_applied": True}

@router.get("/get-saved-jobs")
async def get_saved_jobs(supabase: Client = Depends(get_supabase_client)):
    try:
        uid = supabase.user.id
        user_data = await retrieve_data("user", uid, supabase_client=supabase)
        job_data = await retrieve_data("job", uid, supabase_client=supabase)
        final_job_data = await retrieve_data("final_job", uid, supabase_client=supabase)
        
        return {
            "uid": uid,
            "user_data": user_data,
            "job_data": job_data,
            "final_job_data": final_job_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving saved jobs: {str(e)}")

from services.interview_session_service import (
    start_session,
    process_user_answer,
    get_or_create_session_queue,
    cleanup_session,
    reset_interview_files,
    read_file_content,
    _get_transcript,
    _get_walkthrough,
    TRANSCRIPT_PATH,
    WALKTHROUGH_PATH,
)
from starlette.responses import StreamingResponse
import json as _json


class StartSessionRequest(BaseModel):
    user_interview_id: str


class UserResponseRequest(BaseModel):
    user_interview_id: str
    text: str
    diagram_url: str | None = None


@router.post("/interview/start-session")
async def interview_start_session(payload: StartSessionRequest):
    """Start an interview session — loads questions and pushes the first question via SSE."""
    try:
        # Ensure queue exists before kicking off the async task
        get_or_create_session_queue(payload.user_interview_id)
        asyncio.create_task(start_session(payload.user_interview_id))
        return {"status": "ok", "message": "Session starting"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start session: {str(e)}")


@router.post("/interview/respond")
async def interview_respond(payload: UserResponseRequest):
    """Submit a user answer — processes and pushes AI reply via SSE."""
    try:
        asyncio.create_task(
            process_user_answer(
                user_interview_id=payload.user_interview_id,
                raw_text=payload.text,
                diagram_url=payload.diagram_url,
            )
        )
        return {"status": "ok", "message": "Response received"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process response: {str(e)}")


@router.get("/interview/events/{user_interview_id}")
async def interview_events(user_interview_id: str):
    """Server-Sent Events stream for pushing real-time interview messages to the frontend."""

    async def event_generator():
        queue = get_or_create_session_queue(user_interview_id)

        # Send an initial connection-confirmed event
        yield f"data: {_json.dumps({'type': 'connected', 'message': 'SSE connection established'})}\n\n"

        try:
            while True:
                try:
                    # Wait for a message with a 30-second timeout (acts as keep-alive interval)
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {_json.dumps(message)}\n\n"

                    # If report is ready or there's a terminal error, close the stream
                    if message.get("type") in ("report_ready",):
                        break
                except asyncio.TimeoutError:
                    # Send a keep-alive comment to prevent connection timeout
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            cleanup_session(user_interview_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/meeting-room/files")
async def get_meeting_files(user_interview_id: str = ""):
    try:
        if user_interview_id:
            transcript = _get_transcript(user_interview_id)
            walkthrough = _get_walkthrough(user_interview_id)
        else:
            transcript = read_file_content(TRANSCRIPT_PATH)
            walkthrough = read_file_content(WALKTHROUGH_PATH)
        return {
            "transcript": transcript,
            "walkthrough": walkthrough
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read meeting files: {str(e)}")

@router.post("/meeting-room/reset")
async def reset_meeting_files(user_interview_id: str = "default"):
    try:
        reset_interview_files(user_interview_id)
        return {"status": "success", "message": "Files reset successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset meeting files: {str(e)}")

