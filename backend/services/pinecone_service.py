import hashlib
import asyncio

from pinecone import Pinecone
from core.config import settings


pc = Pinecone (api_key=settings.PINECONE_API_KEY)

# create index 
index_name = "job-matching-index"

# embed job infomation
async def embed_job_data(job_data: list[dict], uid: str):

    if not pc.has_index(index_name):
        pc.create_index_for_model(
            name=index_name,
            cloud="aws",
            region="us-east-1",
            embed={
                "model": "llama-text-embed-v2",
                "field_map": {"text": "chunk_text"}
            }
        )

    dense_index = pc.Index(index_name)

    # Always clear old data — delete is idempotent, saves a blocking describe_index_stats() call
    try:
        await asyncio.to_thread(dense_index.delete, delete_all=True, namespace=uid)
        print(f"Cleared existing data for user: {uid}")
    except Exception:
        pass  # No data to delete or namespace doesn't exist — safe to continue

    # list of all job record
    structure_job = []

    def build_metadata(job_dict, chunk_type, has_salary, min_val, max_val):
        raw = {
            "job_id": job_dict.get("job_id"),
            "chunk_type": chunk_type,
            "title": job_dict.get("title"),
            "work_model": "Remote" if job_dict.get("work_from_home") == True else "On-site",
            "min_experience_years": job_dict.get("minimum_years_experience") or 0,
            "has_salary": has_salary,
            "min_salary": min_val if min_val is not None else 0,
            "max_salary": max_val if max_val is not None else 0
        }
        # Pinecone does not accept None in metadata, filter them out
        return {k: v for k, v in raw.items() if v is not None}

    for each_job in job_data:
        if each_job is None:
            continue

        # Skip jobs that failed AI extraction (no core_skills = raw SerpApi data)
        if not each_job.get("core_skills") and not each_job.get("key_responsibilities"):
            print(f"WARNING: Skipping embed for job '{each_job.get('title')}' — missing extracted fields")
            continue

        # Determine if the job actually has salary data
        salary_parsed = each_job.get("salary_parsed") or {}
        min_val = salary_parsed.get("min_salary")
        max_val = salary_parsed.get("max_salary")
        
        # Handle cases where only one boundary is provided
        if min_val is not None and max_val is None:
            max_val = min_val
        elif max_val is not None and min_val is None:
            min_val = max_val
            
        has_salary = bool(min_val is not None or max_val is not None)

        # Pinecone does not accept None in metadata, filter them out
        metadata = build_metadata(each_job, "skills", has_salary, min_val, max_val)

        job_id_str = str(each_job.get("job_id") or "")
        hashed_job_id = hashlib.md5(job_id_str.encode('utf-8')).hexdigest()

        each_job_skill = {
            "id": f"{hashed_job_id}_skills",
            "chunk_text": f"Technical and soft skills required for {each_job.get('title')} : {', '.join(each_job.get('core_skills') or [])}, {', '.join(each_job.get('soft_skills') or [])}",
        }

        # Flatten metadata into the record itself
        for k, v in metadata.items():
            each_job_skill[k] = v

        resp_metadata = build_metadata(each_job, "responsibilities", has_salary, min_val, max_val)

        structure_job.append(each_job_skill)

        responsibilities = each_job.get('key_responsibilities') or []
        
        # Group responsibilities into chunks of 2-3 to balance context and specificity
        chunk_size = 2
        for i in range(0, len(responsibilities), chunk_size):
            resp_chunk = responsibilities[i:i + chunk_size]
            resp_text = " ".join(resp_chunk)
            
            each_job_resp = {
                "id": f"{hashed_job_id}_resp_{i}",
                "chunk_text": f"Job responsibility: {resp_text}",
            }
            # Flatten metadata into the record itself
            for k, v in resp_metadata.items():
                each_job_resp[k] = v
            structure_job.append(each_job_resp)

    # limit the upsert per batch
    for i in range(0, len(structure_job), 90):
        batch = structure_job[i : i+90]

        # upsert records into namespace
        await asyncio.to_thread(dense_index.upsert_records, namespace=uid, records=batch)

        print(f"Batch {i} to {i+len(batch)} successfully upserted")

    # Brief wait for serverless Pinecone to index upserted vectors (~1-2s typical)
    await asyncio.sleep(2)
    print("Successfully executed embed_job_data")

# organise user data before vector searching
async def organise_user_data(user_data: dict, uid: str):
    if not user_data:
        raise ValueError("No user data provided to organise.")

    # 1. Extract ONLY competencies for the Skills query
    competencies_list = (user_data.get('primary_competencies') or []) + (user_data.get('secondary_competencies') or [])
    skills_query = f"Candidate technical and soft skills: {', '.join(competencies_list)}"

    # 2. Extract INDIVIDUAL experiences
    experience_queries = []
    for each_exp in (user_data.get("experience_and_projects") or []):
        if each_exp is None:
            continue
        
        exp_txt = f"Experience as {each_exp.get('title')}"
        if each_exp.get("domain"): exp_txt += f" in {each_exp.get('domain')}."
        if each_exp.get("technologies"): exp_txt += f" Used {', '.join(each_exp.get('technologies'))}."
        if each_exp.get("impact_and_scale"): exp_txt += f" Impact: {each_exp.get('impact_and_scale')}."
        
        experience_queries.append(exp_txt)

    # Ensure we get a default of 0 if expected_salary is missing
    target_salary = user_data.get("expected_salary") or 0

    # 3. Pass granular data to search function
    ranked_job_id = await search_match_job(
        skills_query=skills_query, 
        experience_queries=experience_queries,
        years_of_experience=user_data.get("years_of_experience") or 0,
        target_salary=target_salary,
        uid=uid
    )
    print("Successfully executed organise_user_data")
    return ranked_job_id

def extract_hits(result_obj):
    """Extract hits from Pinecone search result, handling both dict and object formats."""
    if isinstance(result_obj, dict):
        hits = (result_obj.get("result") or {}).get("hits", [])
    else:
        result_inner = getattr(result_obj, "result", None)
        hits = getattr(result_inner, "hits", []) if result_inner else []
        if not hits:
            print(f"WARNING: Pinecone search returned 0 hits. Response type: {type(result_obj)}")
    return hits

# perform vector searching 
async def search_match_job(skills_query: str, experience_queries: list, years_of_experience: int, target_salary: int, uid: str):
    dense_index = pc.Index(index_name)
    
    # 1. Create a unified base filter
    base_filter = {
        "$and": [
            # Experience condition: Job min experience <= Candidate's years of experience
            {"min_experience_years": {"$lte": years_of_experience}},
            
            # Salary condition: (Job has NO salary) OR (Job max salary >= Candidate's target salary)
            {"$or": [
                {"has_salary": {"$eq": False}}, 
                {"max_salary": {"$gte": target_salary}} 
            ]}
        ]
    }
    
    # 2. Apply to Skills Filter
    skills_filter = {
        "$and": [
            {"chunk_type": {"$eq": "skills"}},
            base_filter
        ]
    }
    
    # 3. Apply to Responsibilities Filter
    resp_filter = {
        "$and": [
            {"chunk_type": {"$eq": "responsibilities"}},
            base_filter
        ]
    }

    all_hit_lists = []

    async def do_search(query_text, search_filter, top_k):
        result = await asyncio.to_thread(
            dense_index.search,
            namespace=uid,
            top_k=top_k,
            inputs={"text": query_text},
            filter=search_filter,
            rerank={"model":"bge-reranker-v2-m3", "top_n": 5, "rank_fields": ["chunk_text"]}
        )
        return extract_hits(result)

    tasks = []

    # 1. Search Skills
    if skills_query.strip():
        tasks.append(do_search(skills_query, skills_filter, 20))

    # 2. Search EACH Experience against Responsibilities
    for exp_query in experience_queries:
        if not exp_query.strip():
            continue
        tasks.append(do_search(exp_query, resp_filter, 10))

    # Wait for all searches to complete concurrently
    results = await asyncio.gather(*tasks)
    
    for hits in results:
        all_hit_lists.append(hits)

    # 3. Dynamic RRF Fusion across all searches
    final_ranked_jobs = reciprocal_rank_fusion(all_hit_lists)

    ranked_job_id = []
    for job in final_ranked_jobs:
        job_id = job['id']
        ranked_job_id.append(job_id)

        # checking purpose
        job_metadata = job.get('metadata') or {}
        job_title = job_metadata.get('title', 'Unknown Title')
        job_score = job.get('rrf_score', 0.0)
        print(f" Job title: {job_title:<40} | Job Score: {job_score:<10}")

    print("Successfully executed search_match_job")
    return ranked_job_id

def reciprocal_rank_fusion(list_of_hit_lists, k=60):
    rrf_scores={}

    # helper function to process each result list
    def process_result(hits_list):
        for rank, hit in enumerate(hits_list, start=1):
            if hit is None:
                continue
            fields = getattr(hit, 'fields', None) or getattr(hit, 'metadata', None)
            if not fields and hasattr(hit, 'get'):
                fields = hit.get('fields') or hit.get('metadata')
            fields = fields or {}

            base_job_id = fields.get('job_id')

            if not base_job_id:
                print(f"WARNING: Hit at rank {rank} has no 'job_id' in metadata: {fields}")
                continue

            if base_job_id not in rrf_scores:
                rrf_scores[base_job_id] = {
                    "id": base_job_id,
                    "rrf_score": 0.0,
                    "metadata": fields
                }

            # add RRF calculation
            rrf_scores[base_job_id]["rrf_score"] += 1.0 / (k + rank)
        print("Successfully executed process_result")

    # Process dynamically
    for hit_list in list_of_hit_lists:
        process_result(hit_list)

    # convert dict to list before sorting
    fused_results = list(rrf_scores.values())
    fused_results.sort(key=lambda x: x['rrf_score'], reverse=True)

    print("Successfully executed reciprocal_rank_fusion")
    return fused_results
