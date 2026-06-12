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
            
    return job

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

        # ReMAP on the ordered job list of dict
        async def remap_job(job):
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    async with rate_limiter:
                        async with sem:
                            remap_result = await asyncio.wait_for(AIOrganiser.job_remap(user_data_dict, job), timeout=60.0)
                            print("Sucessfully executed remap_job")
                            return remap_result
                except asyncio.TimeoutError:
                    print(f"Attempt {attempt + 1} timed out for remap_job (job_id: {job.get('job_id')}) after 60s")
                    if attempt == max_retries - 1:
                        return job
                except Exception as e:
                    print(f"Attempt {attempt + 1} failed for remap_job (job_id: {job.get('job_id')}): {e}")
                    if attempt == max_retries - 1:
                        return job
                    await asyncio.sleep(2 ** attempt)
            return job  # Explicit fallback if all retries exhaust without returning

        remap_tasks = [remap_job(job) for job in completed_ordered_job]

        raw_remap_results = await asyncio.gather(*remap_tasks, return_exceptions=True)

        remap_results_list = []
        for i, result in enumerate(raw_remap_results):
            if isinstance(result, Exception):
                print(f"WARNING: ReMAP failed for job index {i}: {result}")
            elif result is not None:
                remap_results_list.append(result)
        
        if remap_tasks and not remap_results_list:
            raise HTTPException(status_code=500, detail="All ReMAP evaluations failed")

        # organise job list based on logical match score
        remap_results_list = [r for r in remap_results_list if r is not None and isinstance(r, dict)]
        remap_results_list.sort(key=lambda x: x.get('logical_match_score', 0), reverse=True)
        final_ordered_job = remap_results_list
        
        # save final ordered job list
        asyncio.create_task(store_data(final_ordered_job, "final_job_data", uid, supabase_client=supabase))

        # send final ordered job list to frontend
        print("Successfully executed analyse_and_match_job")
        return {"jobs": final_ordered_job, "remap_applied": True}

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
