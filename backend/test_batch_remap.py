import asyncio
import os
import sys

# Add backend to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
# Load .env from root
root_env = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(root_env)

# Also try loading from backend dir just in case
load_dotenv()

from services.AI_extract_service import AIOrganiser
import json

async def test_remap():
    user_data = {
        "education": ["Bachelor of Computer Science"],
        "experience": ["2 years as Software Engineer", "Python, Docker, AWS"]
    }
    
    batch_job_data = [
        {
            "job_id": "job_1",
            "title": "Software Engineer",
            "core_skills": ["Python", "Kubernetes"],
            "soft_skills": ["Teamwork"],
            "key_responsibilities": ["Develop APIs", "Manage Kubernetes clusters"],
            "minimum_years_experience": "3"
        },
        {
            "job_id": "job_2",
            "title": "Frontend Developer",
            "core_skills": ["React", "TypeScript"],
            "soft_skills": ["Communication"],
            "key_responsibilities": ["Build UI components"],
            "minimum_years_experience": "1"
        }
    ]
    
    print("Testing job_batch_remap with gemini-1.5-flash...")
    try:
        result = await AIOrganiser.job_batch_remap(user_data, batch_job_data)
        print("Result:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_remap())
