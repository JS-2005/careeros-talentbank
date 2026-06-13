import uuid
import asyncio
from typing import List, Union
from pydantic import BaseModel
from fastapi import HTTPException
from supabase import create_client, Client
from core.config import settings

# Create a module-level cached Supabase client
_supabase = None

def _get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    return _supabase

async def store_data(data: Union[BaseModel, List[dict], dict], data_type: str, uid: str, supabase_client: Client = None):
    """
    Stores data to Supabase. Runs synchronous calls in a background thread to prevent event loop blocking.
    - data_type == 'user_data': upsert user profile into user_data table.
    - data_type in ['job_data', 'final_job_data']: delete user's existing job records of this type,
      and batch insert the new job records into user_jobs table.
    """
    supabase = supabase_client if supabase_client is not None else _get_supabase()
    
    def _sync_store():
        if data_type == "user_data":
            payload = data if isinstance(data, dict) else data.model_dump()
            supabase.table("user_data").upsert({
                "user_id": uid,
                "data": payload
            }).execute()
            
        elif data_type in ["job_data", "final_job_data"]:
            is_final = (data_type == "final_job_data")
            
            # 1. Delete existing jobs for this user and type
            supabase.table("user_jobs").delete().eq("user_id", uid).eq("is_final", is_final).execute()
            
            # 2. Prepare rows for batch insert
            rows = []
            for job_result in data:
                job_id = job_result.get('job_id')
                if not job_id:
                    job_id = str(uuid.uuid4())
                    job_result['job_id'] = job_id
                    print(f"WARNING: Job missing job_id, generated fallback: {job_id}")
                
                rows.append({
                    "user_id": uid,
                    "job_id": job_id,
                    "is_final": is_final,
                    "data": job_result
                })
            
            # 3. Batch insert if there are rows
            if rows:
                supabase.table("user_jobs").insert(rows).execute()

    try:
        await asyncio.to_thread(_sync_store)
        print("Data stored successfully")
        print("Successfully executed store_data")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error storing data to Supabase: {str(e)}")

async def retrieve_data(type_retrieve: str, uid: str, job_id_list: List[str] = None, supabase_client: Client = None):
    """
    Retrieves data from Supabase. Runs synchronous calls in a background thread to prevent event loop blocking.
    - type_retrieve == 'user': fetch from user_data table.
    - type_retrieve == 'job': fetch initial jobs from user_jobs table.
    - type_retrieve == 'final_job': fetch final jobs from user_jobs table.
    """
    supabase = supabase_client if supabase_client is not None else _get_supabase()
    
    def _sync_retrieve():
        if type_retrieve == "user":
            response = supabase.table("user_data").select("data").eq("user_id", uid).execute()
            if response.data:
                return response.data[0]["data"]
            return None
            
        elif type_retrieve == "job":
            if job_id_list is None:
                # Retrieve all jobs for this user where is_final = False
                response = supabase.table("user_jobs").select("data").eq("user_id", uid).eq("is_final", False).execute()
                jobs = [row["data"] for row in response.data]
                # Re-apply target_job_role grouping lost by Postgres insertion ordering
                jobs.sort(key=lambda x: x.get('target_job_role', ''))
                return jobs
            else:
                # Retrieve jobs with specific job_ids
                response = supabase.table("user_jobs").select("data").eq("user_id", uid).eq("is_final", False).in_("job_id", job_id_list).execute()
                jobs = [row["data"] for row in response.data]
                
                # Order jobs according to job_id_list
                job_map = {job.get('job_id'): job for job in jobs if job.get('job_id')}
                ordered = [job_map[jid] for jid in job_id_list if jid in job_map]
                return ordered
                
        elif type_retrieve == "final_job":
            response = supabase.table("user_jobs").select("data").eq("user_id", uid).eq("is_final", True).execute()
            jobs = [row["data"] for row in response.data]
            # Re-apply logical_match_score sort
            jobs.sort(key=lambda x: x.get('logical_match_score', 0), reverse=True)
            return jobs
            
        else:
            raise ValueError(f"Unknown type_retrieve: '{type_retrieve}'. Expected 'user', 'job', or 'final_job'.")

    try:
        return await asyncio.to_thread(_sync_retrieve)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving data from Supabase: {str(e)}")

async def clear_all_user_data(uid: str, supabase_client: Client = None):
    """
    Clears all database entries for the user from both user_jobs and user_data tables.
    Runs synchronous calls in a background thread to prevent event loop blocking.
    """
    supabase = supabase_client if supabase_client is not None else _get_supabase()
    
    def _sync_clear():
        # Delete user's job entries
        supabase.table("user_jobs").delete().eq("user_id", uid).execute()
        # Delete user's profile entry
        supabase.table("user_data").delete().eq("user_id", uid).execute()

    try:
        await asyncio.to_thread(_sync_clear)
        print(f"Successfully cleared all data for user {uid}")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing data from Supabase: {str(e)}")

# --- AI Interview Operations ---

_supabase_service_role = None

def _get_service_role_supabase() -> Client:
    global _supabase_service_role
    if _supabase_service_role is None:
        if not settings.SUPABASE_SERVICE_ROLE_KEY:
            print("WARNING: SUPABASE_SERVICE_ROLE_KEY is missing. Using standard public key client.")
            _supabase_service_role = _get_supabase()
        else:
            _supabase_service_role = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    return _supabase_service_role

async def create_interview_session(uid: str, target_job_title: str, target_job_id: str = None, target_company_name: str = None, supabase_client: Client = None) -> str:
    supabase = supabase_client if supabase_client is not None else _get_supabase()
    
    def _sync():
        res = supabase.table("interview_sessions").insert({
            "candidate_user_id": uid,
            "target_job_title": target_job_title,
            "target_job_id": target_job_id,
            "target_company_name": target_company_name,
            "status": "in_progress"
        }).execute()
        return res.data[0]["id"]
    return await asyncio.to_thread(_sync)

async def submit_interview_answers(uid: str, session_id: str, consent_given: bool, answers: list, supabase_client: Client = None):
    supabase = supabase_client if supabase_client is not None else _get_supabase()
    
    def _sync():
        from datetime import datetime, timezone
        # 1. verify session ownership
        session_res = supabase.table("interview_sessions").select("id, status").eq("id", session_id).eq("candidate_user_id", uid).execute()
        if not session_res.data:
            raise HTTPException(status_code=403, detail="Session not found or not owned by user")
        
        if session_res.data[0]["status"] != "in_progress":
            raise HTTPException(status_code=409, detail="Interview session already submitted")
            
        if not consent_given:
            raise HTTPException(status_code=400, detail="Consent is required before submitting interview answers")
        
        # 2. insert answers
        if answers:
            answers_data = [
                {
                    "interview_session_id": session_id,
                    "question": a.question,
                    "answer_text": a.answer_text,
                    "answer_order": a.answer_order
                } for a in answers
            ]
            supabase.table("interview_answers").insert(answers_data).execute()
            
        # 3. update session
        supabase.table("interview_sessions").update({
            "consent_given": consent_given,
            "consent_given_at": datetime.now(timezone.utc).isoformat() if consent_given else None,
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", session_id).execute()
        
    await asyncio.to_thread(_sync)

async def get_interview_answers(session_id: str, supabase_client: Client = None) -> list:
    # Service role or user client used to fetch answers for report generation
    supabase = supabase_client if supabase_client is not None else _get_service_role_supabase()
    def _sync():
        res = supabase.table("interview_answers").select("*").eq("interview_session_id", session_id).order("answer_order").execute()
        return res.data
    return await asyncio.to_thread(_sync)

async def update_interview_session_status(session_id: str, status: str, supabase_client: Client = None):
    supabase = supabase_client if supabase_client is not None else _get_service_role_supabase()
    def _sync():
        supabase.table("interview_sessions").update({"status": status}).eq("id", session_id).execute()
    await asyncio.to_thread(_sync)

async def create_interview_report(session_id: str, uid: str, target_job_title: str, report_json: dict, overall_score: int, recommendation: str, status: str = 'generated', error: str = None, supabase_client: Client = None) -> str:
    supabase = supabase_client if supabase_client is not None else _get_service_role_supabase()
    def _sync():
        data = {
            "interview_session_id": session_id,
            "candidate_user_id": uid,
            "target_job_title": target_job_title,
            "report_json": report_json,
            "overall_score": overall_score,
            "recommendation": recommendation,
            "status": status,
            "generation_error": error
        }
        res = supabase.table("interview_reports").insert(data).execute()
        return res.data[0]["id"]
    return await asyncio.to_thread(_sync)

async def get_interview_report(report_id: str, uid: str, supabase_client: Client = None) -> dict:
    supabase = supabase_client if supabase_client is not None else _get_supabase()
    def _sync():
        res = supabase.table("interview_reports").select("*").eq("id", report_id).eq("candidate_user_id", uid).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="Report not found")
        return res.data[0]
    return await asyncio.to_thread(_sync)

async def list_interview_reports(uid: str, supabase_client: Client = None) -> list:
    supabase = supabase_client if supabase_client is not None else _get_supabase()
    def _sync():
        res = supabase.table("interview_reports").select("id, target_job_title, overall_score, recommendation, created_at, status").eq("candidate_user_id", uid).order("created_at", desc=True).execute()
        return res.data
    return await asyncio.to_thread(_sync)
