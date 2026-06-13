from pydantic import BaseModel, Field
from typing import List, Optional

# --- Request/Response Models ---

class CreateSessionRequest(BaseModel):
    target_job_title: str = Field(min_length=1)
    target_job_id: Optional[str] = None
    target_company_name: Optional[str] = None

class CreateSessionResponse(BaseModel):
    session_id: str

class AnswerItem(BaseModel):
    question: str = Field(min_length=5)
    answer_text: str = Field(min_length=20)
    answer_order: int = Field(ge=1)

class SubmitAnswersRequest(BaseModel):
    consent_given: bool
    answers: List[AnswerItem] = Field(min_length=5, max_length=7)

class GenerateReportRequest(BaseModel):
    session_id: str

class GenerateReportResponse(BaseModel):
    report_id: str
    status: str

# --- Gemini Generation Schemas ---

class CandidateOverview(BaseModel):
    name: str = Field(default="Candidate")
    applied_role: str = Field(default="Unknown Role")
    interview_date: str = Field(default="")

class ScoreBreakdown(BaseModel):
    communication: int = Field(ge=0, le=100)
    technical_understanding: int = Field(ge=0, le=100)
    problem_solving: int = Field(ge=0, le=100)
    role_fit: int = Field(ge=0, le=100)
    confidence_and_clarity: int = Field(ge=0, le=100)

class PointEvidence(BaseModel):
    point: str
    evidence: str

class InterviewReportResult(BaseModel):
    candidate_overview: CandidateOverview
    executive_summary: str = Field(default="")
    overall_score: int = Field(ge=0, le=100)
    recommendation: str = Field(default="")
    score_breakdown: ScoreBreakdown
    strengths: List[PointEvidence] = Field(default_factory=list)
    weaknesses: List[PointEvidence] = Field(default_factory=list)
    follow_up_questions: List[str] = Field(default_factory=list)
    final_recommendation: str = Field(default="")
    responsible_ai_disclaimer: str = Field(default="This AI Interview Report is a decision-support tool. It does not replace human recruiters, interviewers, or final hiring decisions.")
