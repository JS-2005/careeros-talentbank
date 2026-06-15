import asyncio
import time
import httpx
from core.config import settings
import serpapi

target_job_role = ["Software Engineer", "Data Scientist", "Product Manager", "DevOps", "Frontend"]

async def fetch_httpx():
    start = time.time()
    async with httpx.AsyncClient(timeout=30.0) as client:
        async def fetch_one(role):
            url = "https://serpapi.com/search.json"
            params = {
                "engine": "google_jobs",
                "q": role,
                "location": "United States",
                "gl": "us",
                "hl": "en",
                "api_key": settings.SERPAPI_API_KEY
            }
            resp = await client.get(url, params=params)
            data = resp.json()
            print(f"Httpx fetched {role}: {len(data.get('jobs_results', []))} jobs")
            return data
                
        await asyncio.gather(*[fetch_one(role) for role in target_job_role])
    print("Httpx time:", time.time() - start)

def search_sync(role):
    client = serpapi.Client(api_key=settings.SERPAPI_API_KEY)
    return client.search({
        "engine": "google_jobs",
        "q": role,
        "location": "United States",
        "gl": "us",
        "hl": "en",
    })

async def fetch_threadpool():
    loop = asyncio.get_running_loop()
    start = time.time()
    results = await asyncio.gather(*[
        loop.run_in_executor(None, search_sync, role)
        for role in target_job_role
    ])
    for i, role in enumerate(target_job_role):
        print(f"Serpapi fetched {role}: {len(results[i].get('jobs_results', []))} jobs")
    print("Threadpool time:", time.time() - start)

async def main():
    await fetch_httpx()
    await fetch_threadpool()

asyncio.run(main())
