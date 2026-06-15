from pydantic import BaseModel, Field
from typing import List

class SalaryInfo(BaseModel):
    min_salary: int | None = Field(
        description="The minimum numeric salary value. For example, convert 'RM 114K' to 114000. If it says 'Up to 11k', set this to null."
    )
    max_salary: int | None = Field(
        description="The maximum numeric salary value. For example, convert 'RM 216K' to 216000. If a single flat rate is given, use that number here."
    )
    currency: str | None = Field(
        description="The standard 3-letter currency code (e.g., 'MYR', 'CAD', 'USD'). Return null if not specified."
    )
    pay_period: str | None = Field(
        description="The frequency of the pay. Must be exactly one of: 'hourly', 'monthly', 'yearly'. Return null if not specified."
    )

class JobRequirements(BaseModel):
    core_skills: List[str] | None= Field(
        default=None,
        description="The technical skills, programming languages, and frameworks required (e.g., 'Java', 'Spring Boot', 'MongoDB')."
    )
    soft_skills: List[str] | None= Field(
        default=None,
        description="Interpersonal or professional traits required (e.g., 'Communication', 'Agile', 'Problem-solving')."
    )
    minimum_years_experience: int = Field(
        default=0,
        description="The minimum years of experience required. Return an integer. If not specified, return 0."
    )
    key_responsibilities: List[str] | None = Field(
        default=None,
        description="A concise list of 3-5 main duties the candidate will perform."
    )
    education_requirement: str | None = Field(
        default=None,
        description="The minimum education level required (e.g., 'Bachelor of Science in Computer Science'). Return null if not specified."
    )
    salary_parsed: SalaryInfo | None = Field(
        default=None,
        description="The structured extraction of the salary information."
    )

class ExtractedJobInfo(JobRequirements):
    job_id: str = Field(description="The exact job_id provided in the input.")

class JobBatchRequirements(BaseModel):
    results: List[ExtractedJobInfo] = Field(description="List of extracted job requirements corresponding to the input jobs.")
