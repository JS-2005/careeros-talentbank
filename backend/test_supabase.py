import asyncio
from services.supabase_service import _get_supabase, clear_all_user_data, store_data, retrieve_data

async def main():
    try:
        print("Testing Supabase Service...")
        uid = "00000000-0000-0000-0000-000000000000" # dummy uuid-like format
        
        # Test 1: Store profile data
        print("Storing user profile data...")
        user_profile = {"full_name": "Test User", "resume_url": "http://example.com/resume.pdf"}
        await store_data(user_profile, "user_data", uid)
        
        # Test 2: Retrieve profile data
        print("Retrieving user profile data...")
        retrieved_profile = await retrieve_data("user", uid)
        print(f"Retrieved profile: {retrieved_profile}")
        assert retrieved_profile == user_profile
        
        # Test 3: Store jobs
        print("Storing job listings...")
        jobs = [{"job_id": "job_1", "title": "Developer"}, {"job_id": "job_2", "title": "Designer"}]
        await store_data(jobs, "job_data", uid)
        
        # Test 4: Retrieve jobs
        print("Retrieving jobs...")
        retrieved_jobs = await retrieve_data("job", uid)
        print(f"Retrieved jobs: {retrieved_jobs}")
        assert len(retrieved_jobs) == 2
        
        # Test 5: Clear data
        print("Clearing all user data...")
        await clear_all_user_data(uid)
        
        # Verify deletion
        print("Verifying deletion...")
        cleared_profile = await retrieve_data("user", uid)
        cleared_jobs = await retrieve_data("job", uid)
        print(f"User profile exists: {cleared_profile is not None}")
        print(f"User jobs count: {len(cleared_jobs) if cleared_jobs else 0}")
        assert cleared_profile is None
        assert not cleared_jobs
        
        print("All Supabase service tests completed successfully!")
    except Exception as e:
        print(f"Test Failed with error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
