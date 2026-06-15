from pydantic import BaseModel, Field

class RemapResult(BaseModel):
    unmatched_mandatory_skills: list[str] | None = Field(
        description=(
            "Identify core required skills, tools, languages, and frameworks from the job description "
            "that are COMPLETELY MISSING from the candidate's profile. Only include items the candidate "
            "has NO evidence of possessing. Output null if no mandatory skills are missing. "
            "CRITICAL RULE: If you intend to mention a missing skill in the 'remap_description', "
            "it MUST be explicitly extracted and listed in this array first."
            "Example: If the JD requires 'Python' and 'Docker', but the candidate only knows Python, output ['Docker']."
        )
    )
    unmatched_responsibilities: list[str] | None = Field(
        description=(
            "Identify core duties and responsibilities from the job description that the candidate "
            "has NO demonstrable experience with. Only include responsibilities where there is zero "
            "evidence in the candidate's profile. Output null if no responsibilities are missing. "
            "CRITICAL RULE: If you intend to mention a missing responsibility in the 'remap_description', "
            "it MUST be explicitly extracted and listed in this array first."
            "Example: If the JD requires 'managing a team of 5+' and the candidate is only an individual contributor, output ['managing a team of 5+']."
        )
    )
    matched_optional_skills: list[str] | None = Field(
        description=(
            "Identify 'nice-to-have' or 'preferred' skills from the job description that the "
            "candidate DOES possess. These must be explicitly marked as optional/preferred in the JD. "
            "Output null if no optional skills are matched. "
            "Example: If the JD states 'experience with AWS is a plus' and the candidate's resume lists AWS, output ['AWS']."
        )
    )
    remap_description: str = Field(
        description=(
           "A strict, single-sentence explanation focusing on what the candidate is MISSING. "
            "Structure: state any critical gaps first, then acknowledge strengths. "
            "CONSISTENCY ENFORCEMENT: Every single missing skill or responsibility you mention in this sentence "
            "MUST perfectly match the items you listed in the 'unmatched_mandatory_skills' and "
            "'unmatched_responsibilities' arrays. Do not mention a gap here if you did not list it above. "
            "Example: 'The candidate lacks the required Docker and Kubernetes experience and has no "
            "CI/CD pipeline experience, but possesses strong Python and SQL skills that align with "
            "the core development requirements.'"
        )
    )
    has_credential_disqualifier: bool = Field(
        default=False,
        description=(
            "CREDENTIAL-ONLY Boolean. This field is about FORMAL CREDENTIALS, never about skills or responsibilities. "
            "Set True ONLY when the candidate is missing a hard credential that cannot be learned on the job: "
            "1) A mandatory university Degree (e.g., 'Must have a Bachelor's in CS' and candidate has no degree), "
            "2) A legally required License or Certification (e.g., CPA, Medical License, Bar Admission), "
            "3) A government Security Clearance, "
            "4) A severe structural years-of-experience deficit (e.g., JD requires 10+ years, candidate has 1 year). "
            "\n\nCRITICAL — The following must ALWAYS return False: "
            "missing programming languages, missing frameworks, missing tools, missing software skills, "
            "missing technical skills, missing soft skills, missing daily job responsibilities, "
            "missing domain knowledge. Even if the candidate lacks EVERY SINGLE required skill, this MUST be False. "
            "\n\nExamples: "
            "• Candidate lacks Python, React, AWS, Docker, Kubernetes, and all 8 listed responsibilities → False "
            "• Candidate has 0 matching skills out of 15 required → False "
            "• Candidate has no experience in the required industry → False "
            "• Candidate lacks a required CPA license → True "
            "• JD says 'Must have PhD in Machine Learning', candidate has no PhD → True "
            "• JD requires 8+ years experience, candidate has 2 years → True"
        )
    )

class RemapResultWithId(RemapResult):
    job_id: str = Field(
        description="The unique identifier of the job being evaluated."
    )

class BatchRemapResult(BaseModel):
    results: list[RemapResultWithId] = Field(
        description="A list containing the gap analysis results for multiple jobs."
    )

