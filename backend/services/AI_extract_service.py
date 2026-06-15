import asyncio
import base64
import json

from fastapi import HTTPException, UploadFile
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from schemas.resume_schema import ResumeSearchData
from schemas.job_schema import JobRequirements
from schemas.remap_schema import RemapResult
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
            file_contents = await asyncio.to_thread(pdf_resume.file.read)
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
            6. DEALBREAKER CONSTRAINT: You are strictly PROHIBITED from setting 'has_dealbreaker_gap' to True due to missing technical skills, programming languages, software tools, frameworks, or daily job responsibilities. You may ONLY use the dealbreaker flag if the candidate is missing a non-negotiable structural requirement (e.g., mandatory University Degree, legal License, Security Clearance, or severe deficit in total years of experience). Even if the candidate lacks every single required skill, 'has_dealbreaker_gap' MUST STILL BE FALSE.

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
            
            # Apply dealbreaker override
            if remap_analysis.has_dealbreaker_gap:
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
