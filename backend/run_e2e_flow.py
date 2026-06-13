import asyncio
import httpx
from supabase import create_client
from core.config import settings

BACKEND_URL = "http://127.0.0.1:8000"
DEV_TOKEN = "dev-token"

async def run_e2e_flow():
    headers = {
        "Authorization": f"Bearer {DEV_TOKEN}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        # Step 1: Create Interview Session
        print("\n[Step 1] Creating interview session...")
        create_payload = {
            "target_job_title": "Senior Backend Engineer",
            "target_company_name": "Google"
        }
        res = await client.post(f"{BACKEND_URL}/api/v1/interview-session/create", json=create_payload, headers=headers)
        print(f"Status: {res.status_code}")
        print(f"Response: {res.json()}")
        assert res.status_code == 200, "Failed to create session"
        session_id = res.json()["session_id"]
        print(f"Created Session ID: {session_id}")

        # Step 2: Submit Answers
        print("\n[Step 2] Submitting interview answers...")
        submit_payload = {
            "consent_given": True,
            "answers": [
                {
                    "question": "Tell us about yourself and why you are interested in this role.",
                    "answer_text": "I am a senior backend developer with extensive experience building REST APIs using Python and FastAPI.",
                    "answer_order": 1
                },
                {
                    "question": "What relevant technical skills or projects make you suitable for this role?",
                    "answer_text": "I specialize in PostgreSQL, Redis caching, microservices, and Docker containerization.",
                    "answer_order": 2
                },
                {
                    "question": "Describe a challenging problem you solved in a project.",
                    "answer_text": "I optimized database queries by adding proper indexes, which reduced latency by over 80 percent.",
                    "answer_order": 3
                },
                {
                    "question": "How do you handle deadlines or unexpected issues?",
                    "answer_text": "I prioritize tasks using agile methodologies and communicate early with stakeholders if blockers arise.",
                    "answer_order": 4
                },
                {
                    "question": "How do you communicate and collaborate in a team?",
                    "answer_text": "I write clear documentation, perform code reviews, and collaborate closely via Slack and GitHub.",
                    "answer_order": 5
                },
                {
                    "question": "What skills do you still need to improve for this role?",
                    "answer_text": "I want to improve my skills in Kubernetes and cloud-native service mesh architectures.",
                    "answer_order": 6
                }
            ]
        }
        res = await client.post(f"{BACKEND_URL}/api/v1/interview-session/{session_id}/submit", json=submit_payload, headers=headers)
        print(f"Status: {res.status_code}")
        print(f"Response: {res.json()}")
        assert res.status_code == 200, "Failed to submit answers"

        # Step 3: Generate Report (calls Gemini API)
        print("\n[Step 3] Generating interview report (this may take a few seconds)...")
        generate_payload = {
            "session_id": session_id
        }
        res = await client.post(f"{BACKEND_URL}/api/v1/interview-report/generate", json=generate_payload, headers=headers)
        print(f"Status: {res.status_code}")
        print(f"Response: {res.json()}")
        assert res.status_code == 200, "Failed to generate report"
        report_id = res.json()["report_id"]
        print(f"Generated Report ID: {report_id}")

        # Step 4: Retrieve Report
        print("\n[Step 4] Retrieving generated report...")
        res = await client.get(f"{BACKEND_URL}/api/v1/interview-report/{report_id}", headers=headers)
        print(f"Status: {res.status_code}")
        report_data = res.json()
        print(f"Overall Score: {report_data.get('overall_score')}")
        print(f"Recommendation: {report_data.get('recommendation')}")
        assert res.status_code == 200, "Failed to retrieve report"
        assert report_data["status"] == "generated", "Report status is not generated"
        
        # Step 5: List Reports
        print("\n[Step 5] Listing all interview reports...")
        res = await client.get(f"{BACKEND_URL}/api/v1/interview-reports", headers=headers)
        print(f"Status: {res.status_code}")
        print(f"Reports Count: {len(res.json())}")
        assert res.status_code == 200, "Failed to list reports"
        
        print("\n--- ALL API E2E TESTS PASSED ---")

if __name__ == "__main__":
    asyncio.run(run_e2e_flow())
