import asyncio
import hashlib
import httpx
from core.config import settings

MAX_JOBS_PER_REQUEST = 15  # Keeps total Gemma calls ≤ 31

async def search_single_role_async(job_role, country, country_abbr, state, is_intern, client: httpx.AsyncClient):
    if is_intern:
        job_role = f"{job_role} internship"

    url = "https://serpapi.com/search.json"
    params = {
        "engine": "google_jobs",
        "q": f"{job_role} in {state}" if state else job_role,
        "location": country,
        "google_domain": "google.com",
        "gl": country_abbr,
        "hl": "en",
        "api_key": settings.SERPAPI_API_KEY
    }
    
    try:
        response = await client.get(url, params=params, timeout=30.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching from SerpApi for role '{job_role}': {e}")
        return {}

async def fetch_job_list(target_job_role: list[str], country: str, country_abbr: str, state: str | None = None, is_intern: bool = False):
    all_clean_match_jobs = []
    seen_job_ids = set()

    # Fire all searches concurrently using httpx.AsyncClient
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[
            search_single_role_async(role, country, country_abbr, state, is_intern, client)
            for role in target_job_role
        ], return_exceptions=True)

    for role, matching_jobs in zip(target_job_role, results):
        if len(all_clean_match_jobs) >= MAX_JOBS_PER_REQUEST:
            break
        if isinstance(matching_jobs, Exception):
            print(f"Error fetching jobs for '{role}': {matching_jobs}")
            continue

        # check if the fetch was successful
        if matching_jobs and "jobs_results" in matching_jobs:
            for job in matching_jobs["jobs_results"]:
                job_id = job.get("job_id")
                title = job.get("title", "")
                company_name = job.get("company_name", "")

                # Semantic key for synthetic ID generation if needed
                semantic_key = f"{title}-{company_name}".lower()

                # Generate a synthetic job_id if missing so it doesn't break Pinecone
                if not job_id:
                    # Include description hash to reduce collision probability
                    desc = job.get("description", "")[:100]
                    unique_key = f"{semantic_key}-{desc}"
                    job_id = hashlib.md5(unique_key.encode('utf-8')).hexdigest()

                # Deduplicate by job_id
                if job_id in seen_job_ids:
                    continue
                
                if title and company_name:
                    seen_job_ids.add(job_id)
                    
                    # Create the clean dictionary AND inject the 'target_job_role'
                    clean_job = {
                        "target_job_role": role,
                        "job_id": job_id,
                        "title": job.get("title"),
                        "company_name": job.get("company_name"),
                        "location": job.get("location"),
                        "salary": (job.get("detected_extensions") or {}).get("salary"),
                        "work_from_home": (job.get("detected_extensions") or {}).get("work_from_home"),
                        "schedule_type": (job.get("detected_extensions") or {}).get("schedule_type"),
                        "source_link": job.get("source_link"),
                        "description": job.get("description")
                    }
                    all_clean_match_jobs.append(clean_job)
                if len(all_clean_match_jobs) >= MAX_JOBS_PER_REQUEST:
                    break

    print(f"Successfully searched jobs concurrently")
    return all_clean_match_jobs[:MAX_JOBS_PER_REQUEST]
