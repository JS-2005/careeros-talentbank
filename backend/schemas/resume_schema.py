from typing import List
from pydantic import BaseModel, Field

class ExperienceItem(BaseModel):
    title: str | None = Field(
        description="Job title, project name, or academic focus. Output null if not explicitly written. (e.g., 'Full Stack Software Developer Intern', 'Museum Artifact Management System', 'Final Year Project')"
    )
    domain: str | None = Field(
        description="The industry sector. Do NOT output job functions like 'Web Development' or 'Software'. Output null if the specific industry cannot be factualized from the text. (e.g., 'DeFi', 'EdTech', 'Semiconductors', 'E-commerce')"
    )
    context: str | None = Field(
        description="A 1-2 sentence summary of the challenge solved, based ONLY on the text provided. Output null if unstated. (e.g., 'Led development of a web-based decision-support tool to perform comparative filtering.')"
    )
    impact_and_scale: str | None = Field(
        description="Measurable outcomes or system scale. Must contain exact numbers or explicit claims from the text. Output null if absent. (e.g., 'Created ERD, defined 10 interrelated entities', 'Delivered on time with A+ grading', 'Managed 50+ event registrations')"
    )
    technologies: List[str] | None = Field(
        description="Technologies explicitly used in THIS specific role. DO NOT guess or import the candidate's general skills list here unless explicitly linked in the text. It is perfectly acceptable for this to be empty []. (e.g., ['Next.js', 'TypeScript', 'MongoDB', 'FastAPI'])"
    )

class ResumeSearchData(BaseModel):
    is_valid_resume: bool = Field(
        description="True if it is a resume, False otherwise. Output the value in boolean format (e.g., True or False)."
    )
    primary_competencies: List[str] | None = Field(
        description="Core technical skills, programming languages, and frameworks explicitly listed in the text or clearly used in major projects. Empty list if none. (e.g., ['React', 'Node.js', 'Python', 'Java'])"
    )
    secondary_competencies: List[str] | None = Field(
        description="All other software, tools (including IDEs, MS Office suites, databases), and minor skills explicitly mentioned in the text. CRITICAL: Between 'primary_competencies' and 'secondary_competencies', you must extract EVERY single technical skill, tool, and software. Do not hallucinate. (e.g., ['Visual Studio Code', 'DaVinci Resolve', 'Oracle SQL*Plus', 'CapCut'])"
    )
    experience_and_projects: List[ExperienceItem] | None = Field(
        description="Chronological history of work and projects. Empty list if none. (e.g., A list of ExperienceItem objects detailing past roles or academic projects)"
    )
    honours_and_awards: List[str] | None = Field(
        description="List of academic achievements and competition awards relevant to professional capability. Format as 'Award Name (Year) - Issuer: Context/Result'. Example: 'Dean\\'s List (2025) - Faculty of Information and Communication Technology: Awarded for maintaining a CGPA above 3.8' or '1st Prize (2026) - Blockchain Ideathon: Developed a winning smart contract application'. Strictly ignore non-academic or non-professional awards. Empty list if none."
    )
    years_of_experience: float = Field(
        description="Calculated total years of professional work experience. Sum the durations of all non-internship roles. Use the current year for 'present' roles."
    )
    growth_intent: List[str] | None = Field(
        description="Candidate's desired future roles or career trajectory. Extract this from 'Objective', 'Summary', or 'About Me' sections. (e.g., ['Aspiring Full Stack Developer', 'Seeking AI Architecture roles'])"
    )
    operational_style: List[str] | None = Field(
        description="Soft skills, working style, or collaboration methods mentioned in the text (e.g., 'cross-functional collaboration', 'agile methodology'). Do not include spoken languages here."
    )
    languages: List[str] | None = Field(
        description="Spoken and written human languages (e.g., English, Malay, Chinese). Do not include programming languages here."
    )
    target_job_roles: List[str] = Field(
        min_length=1,
        description="A list of standard, highly searchable job titles representing the candidate's career objectives. If the text explicitly states desired roles, extract and standardize them. If NO roles are explicitly mentioned, you MUST analyze the candidate's  competencies and experience to infer and generate 3 broad, industry-standard job titles (e.g., ['Software Engineer', 'Data Analyst', 'IT Support', 'Web Developer']). This list MUST contain at least one valid job search term and cannot be empty."
    )
