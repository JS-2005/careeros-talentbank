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
from services.supabase_service import store_data, retrieve_data, clear_all_user_data, check_cached_remap, upsert_job_batch
from services.job_fetcher import fetch_job_list

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

    if file is None and not search_query:
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

        # prepare job search info
        job_search_info = resume_result.target_job_roles
        auto_match_enabled = True

    else:
        job_search_info = [search_query]

    # Fetch Raw Jobs from SerpApi
    raw_job_result = await fetch_job_list(job_search_info, country, country_abbr, state, is_intern)

    # Prepare user data to send back (only exists if a resume was uploaded)
    if file is not None:
        user_data_dict = resume_result.model_dump()
        if expected_salary is not None:
            user_data_dict["expected_salary"] = expected_salary
    
    # RETURN IMMEDIATELY (Do NOT do Gemma extraction here)
    return {
        "uid": uid,
        "user_data_dict": user_data_dict,
        "raw_job_result": raw_job_result, # Frontend will display this immediately!
        "auto_match_enabled": auto_match_enabled
    }

class SingleJobExtractRequest(BaseModel):
    raw_job: Dict[str, Any]

@router.post("/extract-single-job")
async def extract_single_job(payload: SingleJobExtractRequest, supabase: Client = Depends(get_supabase_client)):
    job = payload.raw_job
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            async with rate_limiter:
                async with sem:
                    # Run Gemma extraction on this single job
                    result = await asyncio.wait_for(AIOrganiser.job_result_extraction(job), timeout=60.0)
                    if result is None:
                        return job # fallback to raw if none
                    return result
        except asyncio.TimeoutError:
            if attempt == max_retries - 1:
                return job # Return original raw job on complete failure
        except Exception as e:
            if attempt == max_retries - 1:
                return job # Return original raw job on complete failure
            await asyncio.sleep(2 ** attempt)
            
            return job # Explicit fallback if all retries exhaust without returning

class BatchJobExtractRequest(BaseModel):
    raw_jobs: List[Dict[str, Any]]

@router.post("/extract-batch-jobs")
async def extract_batch_jobs(payload: BatchJobExtractRequest, supabase: Client = Depends(get_supabase_client)):
    jobs = payload.raw_jobs
    if not jobs:
        return []
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with rate_limiter:
                async with sem:
                    results = await asyncio.wait_for(AIOrganiser.batch_job_result_extraction(jobs), timeout=60.0)
                    if results:
                        return results
                    return jobs
        except asyncio.TimeoutError:
            if attempt == max_retries - 1:
                return jobs
        except Exception as e:
            if attempt == max_retries - 1:
                return jobs
            await asyncio.sleep(2 ** attempt)
            
    return jobs

class RemapBatchRequest(BaseModel):
    user_data_dict: Dict[str, Any]
    jobs_to_evaluate: List[Dict[str, Any]]

@router.post("/remap-batch-jobs")
async def remap_batch_jobs(payload: RemapBatchRequest, supabase: Client = Depends(get_supabase_client)):
    uid = supabase.user.id
    user_data_dict = payload.user_data_dict
    jobs_list = payload.jobs_to_evaluate
    if not jobs_list:
        return {"jobs": []}

    job_ids = [job.get("job_id") for job in jobs_list if job.get("job_id")]
    
    cached_jobs = await check_cached_remap(uid, job_ids, supabase_client=supabase)
    cached_job_ids = {job["job_id"]: job for job in cached_jobs if job.get("job_id")}
    
    jobs_to_process = []
    final_results = []
    
    for job in jobs_list:
        if job.get("job_id") in cached_job_ids:
            final_results.append(cached_job_ids[job["job_id"]])
        else:
            jobs_to_process.append(job)
            
    if not jobs_to_process:
        return {"jobs": final_results}

    BATCH_SIZE = 5
    batches = [jobs_to_process[i:i + BATCH_SIZE] for i in range(0, len(jobs_to_process), BATCH_SIZE)]
    
    async def process_batch(chunk):
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with rate_limiter:
                    async with sem:
                        res = await asyncio.wait_for(AIOrganiser.batch_job_remap(user_data_dict, chunk), timeout=60.0)
                        return res
            except asyncio.TimeoutError:
                if attempt == max_retries - 1:
                    return chunk
            except Exception as e:
                if attempt == max_retries - 1:
                    return chunk
                await asyncio.sleep(2 ** attempt)
        return chunk
        
    batch_tasks = [process_batch(chunk) for chunk in batches]
    raw_remap_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
    
    new_final_jobs = []
    for res in raw_remap_results:
        if isinstance(res, Exception):
            pass
        elif isinstance(res, list):
            new_final_jobs.extend(res)
            
    if new_final_jobs:
        asyncio.create_task(upsert_job_batch(new_final_jobs, True, uid, supabase_client=supabase))
        final_results.extend(new_final_jobs)
        
    return {"jobs": final_results}

@router.post("/remap-and-sort-jobs")
async def remap_n_sort_jobs(payload: RemapJobsRequest, supabase: Client = Depends(get_supabase_client)):
    uid = supabase.user.id
    user_data_dict = payload.user_data_dict
    organised_job_result = payload.organised_job_result

    if not user_data_dict:
        print("No user data provided. Skipping ReMAP and returning organised jobs.")
        try:
            # Save the job data to database so it can be retrieved on page refresh
            await asyncio.gather(
                store_data(organised_job_result, "job_data", uid, supabase_client=supabase),
                store_data(organised_job_result, "final_job_data", uid, supabase_client=supabase)
            )
            print("Successfully stored job data without user resume")
        except Exception as e:
            print(f"Error storing job data: {e}")
        return {"jobs": organised_job_result, "remap_applied": False}

    try:
        # Concurrently save the job and resume data, and embed job data to Pinecone.
        await asyncio.gather(
            # save organised job list
            store_data(organised_job_result, "job_data", uid, supabase_client=supabase),

            # embed organised job list to pinecone directly
            embed_job_data(organised_job_result, uid),

            # save resume result
            store_data(user_data_dict, "user_data", uid, supabase_client=supabase),
        )

        ordered_job_list = await asyncio.to_thread(organise_user_data, user_data_dict, uid)

        # Create a dictionary for instant lookups using the data you ALREADY fetched
        for idx, job in enumerate(organised_job_result):
            if not job.get('job_id'):
                job['job_id'] = f"fallback_{uuid.uuid4().hex[:8]}"
                print(f"WARNING: Job at index {idx} has no job_id. Assigned: {job['job_id']}")
        job_dict = {job.get('job_id'): job for job in organised_job_result if job.get('job_id')}

        # Build the completed_ordered_job list using the sorted IDs from Pinecone
        completed_ordered_job = []
        for j_id in ordered_job_list:
            if j_id in job_dict:
                completed_ordered_job.append(job_dict[j_id])

        # Guard: if Pinecone returned no matching jobs, return what we have without ReMAP scores
        if not completed_ordered_job:
            print("WARNING: Pinecone returned 0 matched jobs. Returning organised_job_result without ReMAP scores.")
            return {"jobs": organised_job_result, "remap_applied": False}

        # Return the jobs sorted by Pinecone immediately for lazy loading
        print("Successfully executed analyse_and_match_job (Pinecone Sort Only)")
        return {"jobs": completed_ordered_job, "remap_applied": False}

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

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

