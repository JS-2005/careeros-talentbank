import asyncio
import hashlib
import serpapi
from core.config import settings

client = serpapi.Client(api_key=settings.SERPAPI_API_KEY)

MAX_JOBS_PER_REQUEST = 15  # Keeps total Gemma calls ≤ 31

def search_single_role(job_role, country, country_abbr, state, is_intern):
    if is_intern:
        job_role = f"{job_role} internship"

    return client.search({
        "engine": "google_jobs",
        "q": f"{job_role} in {state}" if state else job_role,
        "location": country,
        "google_domain": "google.com",
        "gl": country_abbr,
        "hl": "en",
    })

async def fetch_job_list(target_job_role: list[str], country: str, country_abbr: str, state: str | None = None, is_intern: bool = False):
    all_clean_match_jobs = []
    seen_job_ids = set()

    loop = asyncio.get_running_loop()
    # Fire all searches concurrently, then process results
    results = await asyncio.gather(*[
        loop.run_in_executor(None, search_single_role, role, country, country_abbr, state, is_intern)
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
