import asyncio
from services.job_fetcher import fetch_job_list

async def test_fetch():
    print("Testing fetch_job_list...")
    target_job_roles = ["Software Engineer", "Data Scientist", "Product Manager"]
    country = "United States"
    country_abbr = "us"
    
    # We will test if the code executes without syntax or runtime errors.
    # It might return [] if SERPAPI_API_KEY is not set (401 error caught).
    try:
        results = await fetch_job_list(
            target_job_role=target_job_roles,
            country=country,
            country_abbr=country_abbr
        )
        print("Success! Results returned:", results)
        print("Test passed.")
    except Exception as e:
        print(f"Error occurred during execution: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_fetch())
