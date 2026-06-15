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
    has_dealbreaker_gap: bool = Field(
        description=(
            "Strict Boolean gate. Output True ONLY if the candidate is missing an absolute "
            "administrative, legal, or structural prerequisite. Valid dealbreakers are strictly "
            "limited to: missing a mandatory University Degree, lacking a required legal "
            "License/Certification (e.g., CPA, RN), lacking required Security Clearance, or a "
            "massive structural deficit in total years of experience (e.g., applying for a Senior "
            "Director role with 0 years of experience). CRITICAL CONSTRAINT: You MUST output False "
            "if the candidate is only missing technical skills, programming languages, software "
            "tools, or daily job responsibilities. Never use missing skills as a dealbreaker."
        )
    )
