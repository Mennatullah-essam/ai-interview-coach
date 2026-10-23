import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import Difficulty, InterviewType, QuestionType
from app.schemas.common import StrictModel, Timestamp, Trimmed

# --- CVs ---------------------------------------------------------------------


class CVOut(BaseModel):
    id: uuid.UUID
    original_filename: str
    extension: str
    size_bytes: int
    parse_status: str
    created_at: Timestamp


class CVExtracted(BaseModel):
    skills: list[str]
    experience: list[str]
    education: list[str]
    projects: list[str]


class CVDetailOut(BaseModel):
    cv: CVOut
    extracted: CVExtracted


class CVPage(BaseModel):
    items: list[CVOut]
    total: int
    limit: int
    offset: int


# --- interviews ------------------------------------------------------------------


class InterviewCreateIn(StrictModel):
    cv_id: uuid.UUID | None = None  # missing -> CV_REQUIRED (checked in the route)
    target_role: Trimmed = Field(min_length=3, max_length=100)
    interview_type: InterviewType
    difficulty: Difficulty
    question_count: Literal[5, 10, 15]
    # Milestone 4 (optional, backwards compatible)
    job_description: str | None = Field(default=None, max_length=5000)
    adaptive: bool = False


class InterviewConfigOut(BaseModel):
    cv_id: uuid.UUID | None
    target_role: str
    interview_type: InterviewType
    difficulty: Difficulty
    question_count: int
    adaptive: bool = False
    max_follow_ups: int = 0
    personalized: bool = False
    has_job_description: bool = False


class QuestionOut(BaseModel):
    id: uuid.UUID
    position: int
    text: str
    type: QuestionType
    state: Literal["pending", "answered", "evaluated"] | None = None
    # Why this question was chosen and what it assesses (Milestone 4).
    category: str | None = None
    reason: str | None = None
    focus_skills: list[str] = []
    parent_question_id: uuid.UUID | None = None
    follow_up_kind: str | None = None


class InterviewCreatedOut(BaseModel):
    id: uuid.UUID
    status: str
    config: InterviewConfigOut
    questions: list[QuestionOut]
    created_at: Timestamp


class Progress(BaseModel):
    answered: int
    evaluated: int
    total: int


class InterviewStateOut(InterviewCreatedOut):
    completed_at: Timestamp | None
    progress: Progress
    current_position: int | None


class StatusOut(BaseModel):
    id: uuid.UUID
    status: str


# --- answers and evaluations ---------------------------------------------------------


class AnswerIn(StrictModel):
    # Length rules are checked in the route so they map to ANSWER_* error codes.
    answer_text: str = Field(max_length=20000)


class AnswerOut(BaseModel):
    id: uuid.UUID
    interview_id: uuid.UUID
    question_id: uuid.UUID
    answer_text: str
    char_count: int
    input_mode: str = "text"
    submitted_at: Timestamp
    updated_at: Timestamp


class CategoryScores(BaseModel):
    relevance: int
    clarity: int
    technical_depth: int
    structure: int


class DimensionOut(BaseModel):
    key: str
    label: str
    score: int | None  # None = not applicable / not assessed
    weight: float
    explanation: str


class ConceptEvidenceOut(BaseModel):
    concept: str
    status: str  # demonstrated | partial | mentioned | missing
    evidence: str | None = None  # the sentence from the answer that supports it
    source: str | None = None  # "llm" when a model review credited it (quote-verified)


class ClaimOut(BaseModel):
    explanation: str
    evidence: str | None = None


class AgentDecisionOut(BaseModel):
    action: str  # continue | clarify | request_example | probe_concept | deepen
    rationale: str
    evidence: list[str] = []
    source: str  # rules | llm
    target_concept: str | None = None
    policy: str  # accepted, or why a proposal was not run


class EvaluationOut(BaseModel):
    id: uuid.UUID
    question_id: uuid.UUID
    overall_score: int
    category_scores: CategoryScores
    strengths: list[str]
    weaknesses: list[str]
    improvement_tip: str
    ideal_answer: str
    feedback_source: str
    scoring_version: str
    created_at: Timestamp
    # Milestone 4 rubric details (empty for evaluations made before Milestone 4)
    dimensions: list[DimensionOut] = []
    missing_concepts: list[str] = []
    suggestions: list[str] = []
    explanation: str | None = None
    ideal_outline: list[str] = []
    # Adaptive interviews: a follow-up inserted after this question, or a later question that was adjusted.
    follow_up: "QuestionOut | None" = None
    replaced_question: "QuestionOut | None" = None
    # Milestone 5: evidence behind the scores, and the agent's decision for this answer.
    concept_evidence: list[ConceptEvidenceOut] = []
    demonstrated_concepts: list[str] = []
    unsupported_claims: list[str] = []
    incorrect_claims: list[ClaimOut] = []
    evidence_level: str | None = None
    agent_decision: AgentDecisionOut | None = None


# --- results, history and performance ---------------------------------------------------------


class InterviewSummary(BaseModel):
    id: uuid.UUID
    completed_at: Timestamp | None
    target_role: str
    interview_type: InterviewType
    difficulty: Difficulty
    question_count: int
    overall_score: int | None
    status: str


class Breakdown(BaseModel):
    structure: int
    relevance: int
    clarity: int
    technical_depth: int
    communication: int


class ResultItemQuestion(BaseModel):
    id: uuid.UUID
    text: str
    type: QuestionType
    category: str | None = None
    reason: str | None = None
    parent_question_id: uuid.UUID | None = None


class ResultItem(BaseModel):
    position: int
    question: ResultItemQuestion
    answer_text: str
    evaluation: EvaluationOut


class ResultsOut(BaseModel):
    interview: InterviewSummary
    breakdown: Breakdown
    additional_strength: str
    additional_improvement: str
    recommendations: list[str]
    generated_by: str
    items: list[ResultItem]


class HistoryPage(BaseModel):
    items: list[InterviewSummary]
    total: int
    limit: int
    offset: int


class SkillScore(BaseModel):
    key: str
    label: str
    score: int


class SkillsOut(BaseModel):
    skills: list[SkillScore]
    interviews_counted: int


class TrendPoint(BaseModel):
    interview_id: uuid.UUID
    completed_at: Timestamp
    overall_score: int


class SummaryOut(BaseModel):
    interviews_completed: int
    average_score: int | None
    strongest_skill: SkillScore | None
    weakest_skill: SkillScore | None
    trend: list[TrendPoint]
