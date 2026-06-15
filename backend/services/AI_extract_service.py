import asyncio
import base64
import json

from fastapi import HTTPException, UploadFile
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from schemas.resume_schema import ResumeSearchData
from schemas.job_schema import JobRequirements, JobBatchRequirements
from schemas.remap_schema import RemapResult, BatchRemapResult
from core.config import settings

# initialise Gemini
_llm_instance = None
_structured_llm_cache = {}
 
def get_llm():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = ChatGoogleGenerativeAI(
            model="gemma-4-31b-it",
            temperature=0,
            google_api_key=settings.GEMINI_API_KEY
        )
    return _llm_instance

def get_structured_llm(schema):
    """Cache structured LLM wrappers to avoid re-creation overhead."""
    global _structured_llm_cache
    schema_name = schema.__name__
    if schema_name not in _structured_llm_cache:
        _structured_llm_cache[schema_name] = get_llm().with_structured_output(schema)
    return _structured_llm_cache[schema_name]

class AIOrganiser:
    @staticmethod
    async def resume_analysis(pdf_resume: UploadFile):
        try:
            # read file and convert to base64
            file_contents = await pdf_resume.read()
            pdf_base64 = base64.b64encode(file_contents).decode('utf-8')

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading file : {str(e)}")

        system_instruct = SystemMessage (
            content="""# Role & Purpose
        You are an expert Resume Extraction AI. Your objective is to extract facts from the provided resume and map them accurately to the structured schema. All information must be grounded solely in the provided resume.

        # Grounding & Synthesis Directives (CRITICAL)
        1. NO EXTERNAL HALLUCINATION: You are strictly prohibited from inventing companies, skills, degrees, or metrics that are not present in the document. 
        2. CROSS-SECTION SYNTHESIS: Resumes often separate information (e.g., listing a tech stack in a general "Skills" section rather than under a specific job). You are permitted and expected to synthesize these sections. If a job description mentions building a "FastAPI backend," you must map "FastAPI" to that role's technologies.
        3. CONTEXTUAL DOMAINS: You may deduce the "domain" or "industry" based on the context of the companies and products mentioned (e.g., identifying "SaaS", "E-commerce", or "Fintech" from the project descriptions).
        4. DEFAULT TO EMPTY: If a piece of data is truly missing and cannot be synthesized from the text, output `null` (for strings) or `[]` (for lists).
        5. ANTI-DUMPING RULE FOR SKILLS: Do not blindly copy a candidate's entire "Skills" section into the `technologies` array of a specific job experience. You may only list a technology under a specific job if the bullet points for that job explicitly name the technology, OR if the explicit nature of the product strictly dictates it. When in doubt, leave the job's `technologies` array empty and rely on the global `primary_competencies` array.
        6. A domain is an industry (e.g., Healthcare, SaaS, E-commerce). "Web Development", "Software Engineering", or "IT" are job functions, not domains. If the industry is not explicitly stated or blatantly obvious from the company description, output null."""
        )

        # structured Gemma output
        structured_llm = get_structured_llm(ResumeSearchData)

        # create multimodal message
        message = HumanMessage(
            content = [
                {
                    "type": "text",
                    "text": "Please analyze the attached PDF document according to your core directives."
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:application/pdf;base64,{pdf_base64}"}
                }
            ]
        )

        try:
            # start analysing resume 
            resume_result = await structured_llm.ainvoke([system_instruct, message])

            print("Successfully executed resume_analysis")
            return resume_result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error analysing resume: {str(e)}")
        
    # extract for individual job result
    @staticmethod
    async def job_result_extraction(job_result):
        # clean job result
        clean_job_result = {
            "title": job_result.get("title"),
            "description": job_result.get("description"),
            "salary": job_result.get("salary")
        }

        # system instruction for job result extraction
        system_instruct = SystemMessage(
            content="""**Role & Objective**
        You are an expert, high-precision data extraction assistant. Your task is to analyze JSON data containing job search results and extract the core requirements, responsibilities, and salary information for each job listing. 

        **CRITICAL: Strict Anti-Hallucination & Source Grounding**
        * **Do not hallucinate.** You must extract data **only** from the provided `job_results` JSON. 
        * Do not use outside knowledge or common sense to guess, infer, or fill in missing information based on the job title or company.
        * If a specific piece of information (e.g., education, salary, years of experience) is not explicitly stated in the job description or metadata, you must return the default empty value (`null`, `[]`, or `0`).

        **Output Format**
        You must return a JSON array of objects, where each object strictly conforms to the following schema. Do not include any explanations, conversational text, or markdown outside of the JSON block."""
        )

        # structured Gemmma Output
        structured_llm = get_structured_llm(JobRequirements)
        
        json_message = json.dumps(clean_job_result)

        # create multimodel message
        message = HumanMessage(
            content = [
                {
                    "type": "text",
                    "text": json_message
                }
            ]
        )

        try:
            # start extracting job info
            extracted_job_info = await structured_llm.ainvoke([system_instruct, message])

            extracted_dict = extracted_job_info.model_dump()
            for key, value in job_result.items():
                if key not in extracted_dict:
                    extracted_dict[key] = value

            print("Successfully executed job_result_extraction")
            return extracted_dict
        except Exception as e:
            print(f"Error extracting job info: {str(e)}")
            return None
        
    # extract for batch job result
    @staticmethod
    async def job_batch_extraction(job_results_batch):
        # clean job results for the batch
        clean_jobs = []
        for job in job_results_batch:
            clean_jobs.append({
                "job_id": job.get("job_id"),
                "title": job.get("title"),
                "description": job.get("description"),
                "salary": job.get("salary")
            })

        # system instruction for job batch extraction
        system_instruct = SystemMessage(
            content="""**Role & Objective**
        You are an expert, high-precision data extraction assistant. Your task is to analyze JSON data containing multiple job search results and extract the core requirements, responsibilities, and salary information for each job listing. 

        **CRITICAL: Strict Anti-Hallucination & Source Grounding**
        * **Do not hallucinate.** You must extract data **only** from the provided JSON. 
        * Do not use outside knowledge or common sense to guess, infer, or fill in missing information based on the job title or company.
        * If a specific piece of information (e.g., education, salary, years of experience) is not explicitly stated in the job description or metadata, you must return the default empty value (`null`, `[]`, or `0`).
        * **ID Mapping:** You MUST ensure that the extracted info accurately maps back to the `job_id` provided for each job.

        **Output Format**
        You must return a JSON object with an array of results, where each object strictly conforms to the provided schema and contains the original `job_id`. Do not include any explanations, conversational text, or markdown outside of the JSON block."""
        )

        # structured Gemma Output for batch
        structured_llm = get_structured_llm(JobBatchRequirements)
        
        json_message = json.dumps({"jobs": clean_jobs})

        # create multimodal message
        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": json_message
                }
            ]
        )

        try:
            # start extracting job info for the batch
            extracted_batch_info = await structured_llm.ainvoke([system_instruct, message])

            # create a lookup dictionary from the LLM results by job_id
            extracted_dict_by_id = {
                item.job_id: item.model_dump(exclude={'job_id'}) 
                for item in extracted_batch_info.results
            }

            # Merge back with the original raw jobs
            final_batch_results = []
            for original_job in job_results_batch:
                job_id = original_job.get("job_id")
                
                if job_id in extracted_dict_by_id:
                    # Merge original job with extracted data
                    merged_job = original_job.copy()
                    for key, value in extracted_dict_by_id[job_id].items():
                        if key not in merged_job:
                            merged_job[key] = value
                    final_batch_results.append(merged_job)
                else:
                    # If LLM skipped it, just return the original
                    final_batch_results.append(original_job)

            print("Successfully executed job_batch_extraction")
            return final_batch_results
        except Exception as e:
            print(f"Error extracting batch job info: {str(e)}")
            return job_results_batch  # fallback to raw jobs on error

    # ReMAP on organised job list
    @staticmethod
    async def job_remap(user_data: dict, job_data: dict):
            
        try:
            system_instruct = SystemMessage(
                content="""You are the Core Extraction and Gap Analysis Engine for a ReMAP (Reasoning-enhanced Multi-turn Agent with Personalized Adaptation) recruitment framework. Your objective is to identify precise GAPS between a Candidate Profile and a Job Description.
            CRITICAL PROCESSING RULES:
            1. THE EXPERIENCE & EDUCATION RULE: Evaluate years of experience strictly based on the timeline provided. For education, evaluate the academic context holistically (e.g., enrollment in an Information and Communication Technology faculty directly satisfies requirements for a Computer Science, Software Engineering, or IT degree).
            2. STRICT EVIDENCE-BASED ANALYSIS: When determining if a candidate LACKS a requirement, you must base your decision ONLY on explicitly stated skills, technologies, and experience in the candidate's profile. If a specific technology, language, or framework (e.g., VB .Net, ASP .NET) is named in the JD, it is COMPLETELY MISSING unless that exact name appears in the candidate profile. 
            - CRITICAL: Broad phrases in the candidate's profile like "multiple programming languages", "web frameworks", or "software development experience" DO NOT satisfy specific technology requirements. Do not infer. If the exact name is not there, it is UNMATCHED.
            - EXCEPTION: You may count a skill as "possessed" ONLY if the candidate's project description explicitly names the technology OR if the project's nature makes it physically impossible to complete without that specific skill (e.g., a "React Native mobile app" inherently requires JavaScript).
            3. MANDATORY VS. OPTIONAL (INTERNSHIP RULE): Focus your gap analysis strictly on core requirements. 
            - You must completely ignore the absence of items explicitly marked as 'preferred', 'nice-to-haves', or 'optional' in the JD.
            - CRITICAL FOR INTERNSHIPS: Do NOT ignore core technologies (like languages or frameworks) just because the JD is for an internship or describes them as "learning opportunities" or "skills you will build upon". If a specific core tech is expected to be used in the role and the candidate doesn't have it yet, it MUST be classified as UNMATCHED.
            4. THE CONSISTENCY MANDATE: There must be absolute alignment between your extracted data arrays and your final description sentence. You cannot mention a missing skill or responsibility in your final sentence unless it is explicitly listed in your unmatched arrays, and vice-versa. 
            5. SEQUENTIAL GAP IDENTIFICATION:
            - First, extract all responsibilities and skills from the JD, separating mandatory from optional.
            - Second, scan the candidate's entire profile for EACH mandatory requirement. If zero evidence is found, add it to the unmatched arrays.
            - Third, synthesize your findings into the single 'remap_description' sentence. State the critical gaps first, then briefly acknowledge the aligned strengths.
            6. CREDENTIAL DISQUALIFIER RULE (has_credential_disqualifier):
            This field is about FORMAL CREDENTIALS ONLY — it has NOTHING to do with skills, tools, frameworks, or responsibilities.
            Set 'has_credential_disqualifier' to True ONLY if the candidate is missing one of these four hard credentials:
              a) A mandatory university Degree explicitly required by the JD (e.g., "Must have Bachelor's in CS")
              b) A legally required License or Certification (e.g., CPA, Medical License, Bar Admission)
              c) A government Security Clearance
              d) A severe structural years-of-experience deficit (e.g., JD requires 10+ years, candidate has 1 year)
            For ALL other gaps — including missing programming languages, frameworks, tools, software, daily responsibilities, domain knowledge, soft skills — 'has_credential_disqualifier' MUST BE False.
            Even if the candidate lacks every single required skill AND every listed responsibility, 'has_credential_disqualifier' MUST STILL BE False.
            EXAMPLE EVALUATIONS:
            - Candidate lacks Python, React, AWS, Docker, Kubernetes (all core skills). Candidate has a CS degree.
            -> has_credential_disqualifier: False (skills are NOT credentials)
            - Candidate is missing 8 out of 8 mandatory daily responsibilities.
            -> has_credential_disqualifier: False (responsibilities are NOT credentials)
            - Candidate has zero matching skills out of 15 required.
            -> has_credential_disqualifier: False (skills are NOT credentials)
            - Candidate lacks required CPA license.
            -> has_credential_disqualifier: True (license IS a credential)
            - JD requires PhD in Machine Learning, candidate has no PhD.
            -> has_credential_disqualifier: True (degree IS a credential)

            OUTPUT CONSTRAINT:
            You must return ONLY the strictly structured JSON matching the provided schema. Do not include markdown formatting, conversational filler, or explanations outside of the JSON object. When in doubt about whether a candidate possesses a skill, conservatively classify it as UNMATCHED."""
            )

            # Structured Gemma output
            structured_llm = get_structured_llm(RemapResult)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error preparing ReMAP evaluation: {str(e)}")
        
        # create multimodel message
        message = HumanMessage(
            content = [
                {
                    "type": "text",
                    "text": f"User Profile Data: {json.dumps(user_data)} \n\n Job Data: {json.dumps(job_data)}"
                }
            ]
        )

        try:
            # start remap evaluation
            remap_analysis = await structured_llm.ainvoke([system_instruct, message])
            print("Successfully executed job_remap")

            # score for each categories
            PENALTY_PER_UNMATCHED_MANDATORY = 10
            PENALTY_PER_UNMATCHED_RESP = 6
            BONUS_PER_MATCHED_OPTIONAL = 2
            base_score = 100

            # get number of unmatched and matched items
            num_unmatched_mandatory = len(remap_analysis.unmatched_mandatory_skills or [])
            num_unmatched_resp = len(remap_analysis.unmatched_responsibilities or [])
            num_matched_optional = len(remap_analysis.matched_optional_skills or [])

            # calculate penalty and bonus
            penalty = (num_unmatched_mandatory * PENALTY_PER_UNMATCHED_MANDATORY) + (num_unmatched_resp * PENALTY_PER_UNMATCHED_RESP)
            bonus = num_matched_optional * BONUS_PER_MATCHED_OPTIONAL

            core_score = base_score - penalty

            if penalty > 0:
                effective_bonus = min(bonus, penalty * 0.3)
                logical_match_score = core_score + effective_bonus
            else:
                logical_match_score = core_score + bonus

            # calculate logical match score
            logical_match_score = max(0, min(100, logical_match_score))
            
            # Apply credential disqualifier override
            if remap_analysis.has_credential_disqualifier:
                logical_match_score = 0
            
            # add new variable to dictionary
            updated_job_data = job_data.copy()
            
            # Merge all AI-extracted fields via model_dump
            extracted_dict = remap_analysis.model_dump()
            for key, value in extracted_dict.items():
                updated_job_data[key] = value

            # the field that needed
            updated_job_data['logical_match_score'] = logical_match_score

            return updated_job_data
        except Exception as e:
            print(f"Error during ReMAP evaluation: {str(e)}")
            return job_data  # Return original job without remap score

    # Batch ReMAP on a list of organised jobs
    @staticmethod
    async def job_batch_remap(user_data: dict, batch_job_data: list[dict]):
        if not batch_job_data:
            return []
            
        try:
            system_instruct = SystemMessage(
                content="""You are the Core Extraction and Gap Analysis Engine for a ReMAP (Reasoning-enhanced Multi-turn Agent with Personalized Adaptation) recruitment framework. Your objective is to identify precise GAPS between a Candidate Profile and multiple Job Descriptions.
            CRITICAL PROCESSING RULES:
            1. THE EXPERIENCE & EDUCATION RULE: Evaluate years of experience strictly based on the timeline provided. For education, evaluate the academic context holistically.
            2. STRICT EVIDENCE-BASED ANALYSIS: When determining if a candidate LACKS a requirement, you must base your decision ONLY on explicitly stated skills, technologies, and experience in the candidate's profile. If a specific technology is named in the JD, it is COMPLETELY MISSING unless that exact name appears.
            3. MANDATORY VS. OPTIONAL: Focus gap analysis strictly on core requirements. Ignore the absence of items explicitly marked as 'preferred' or 'optional' in the JD.
            4. THE CONSISTENCY MANDATE: There must be absolute alignment between your extracted data arrays and your final description sentence. You cannot mention a missing skill/responsibility in your final sentence unless it is explicitly listed in your unmatched arrays, and vice-versa.
            5. CREDENTIAL DISQUALIFIER RULE (has_credential_disqualifier):
            This field is about FORMAL CREDENTIALS ONLY — it has NOTHING to do with skills, tools, frameworks, or responsibilities.
            Set 'has_credential_disqualifier' to True ONLY if the candidate is missing:
              a) A mandatory university Degree, b) A legally required License/Certification, c) A Security Clearance, d) A severe structural years-of-experience deficit.
            For ALL other gaps — including missing programming languages, frameworks, tools, software, daily responsibilities, domain knowledge — 'has_credential_disqualifier' MUST BE False.
            Even if the candidate has ZERO matching skills and ZERO matching responsibilities, 'has_credential_disqualifier' MUST STILL BE False.
            6. MULTI-JOB BATCHING: You will evaluate a list of jobs simultaneously against the single Candidate Profile. You MUST ensure that the output strictly maps back to the `job_id` provided for each job.

            OUTPUT CONSTRAINT:
            You must return ONLY the strictly structured JSON matching the provided schema `BatchRemapResult`. Do not include markdown formatting, conversational filler, or explanations outside of the JSON object. When in doubt about whether a candidate possesses a skill, conservatively classify it as UNMATCHED."""
            )

            # Structured Gemma output
            structured_llm = get_structured_llm(BatchRemapResult)
        except Exception as e:
            print(f"Error preparing Batch ReMAP evaluation: {str(e)}")
            return batch_job_data
        
        # Prepare lightweight job data to save tokens
        clean_jobs = []
        for job in batch_job_data:
            clean_jobs.append({
                "job_id": job.get("job_id"),
                "title": job.get("title"),
                "core_skills": job.get("core_skills"),
                "soft_skills": job.get("soft_skills"),
                "key_responsibilities": job.get("key_responsibilities"),
                "minimum_years_experience": job.get("minimum_years_experience")
            })

        message = HumanMessage(
            content=[
                {
                    "type": "text",
                    "text": f"User Profile Data: {json.dumps(user_data)}\n\nJobs Data: {json.dumps(clean_jobs)}"
                }
            ]
        )

        try:
            # start batch remap evaluation
            remap_analysis = await structured_llm.ainvoke([system_instruct, message])
            print("Successfully executed job_batch_remap")

            # create a lookup dictionary from the LLM results by job_id
            extracted_dict_by_id = {
                item.job_id: item.model_dump(exclude={'job_id'})
                for item in remap_analysis.results
            }

            final_batch_results = []
            for job in batch_job_data:
                job_id = job.get("job_id")
                
                updated_job_data = job.copy()
                
                if job_id in extracted_dict_by_id:
                    result_dict = extracted_dict_by_id[job_id]
                    
                    # Merge all AI-extracted fields
                    for key, value in result_dict.items():
                        updated_job_data[key] = value

                    # calculate score
                    PENALTY_PER_UNMATCHED_MANDATORY = 10
                    PENALTY_PER_UNMATCHED_RESP = 6
                    BONUS_PER_MATCHED_OPTIONAL = 2
                    base_score = 100

                    num_unmatched_mandatory = len(result_dict.get('unmatched_mandatory_skills') or [])
                    num_unmatched_resp = len(result_dict.get('unmatched_responsibilities') or [])
                    num_matched_optional = len(result_dict.get('matched_optional_skills') or [])

                    penalty = (num_unmatched_mandatory * PENALTY_PER_UNMATCHED_MANDATORY) + (num_unmatched_resp * PENALTY_PER_UNMATCHED_RESP)
                    bonus = num_matched_optional * BONUS_PER_MATCHED_OPTIONAL

                    core_score = base_score - penalty

                    if penalty > 0:
                        effective_bonus = min(bonus, penalty * 0.3)
                        logical_match_score = core_score + effective_bonus
                    else:
                        logical_match_score = core_score + bonus

                    logical_match_score = max(0, min(100, logical_match_score))
                    
                    if result_dict.get('has_credential_disqualifier'):
                        logical_match_score = 0
                        
                    updated_job_data['logical_match_score'] = logical_match_score
                else:
                    # If LLM missed this job, default score
                    updated_job_data['logical_match_score'] = 0

                final_batch_results.append(updated_job_data)

            return final_batch_results

        except Exception as e:
            print(f"Error during Batch ReMAP evaluation: {str(e)}")
            return batch_job_data  # fallback
