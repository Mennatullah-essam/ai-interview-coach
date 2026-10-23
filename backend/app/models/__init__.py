"""Import every model here so Base.metadata knows about all tables.

Alembic's env.py imports this package; add new model modules below.
"""

from app.models.auth import RefreshToken
from app.models.cv import CV
from app.models.intelligence import AgentDecisionRecord, CandidateProfile, ImprovementPlan
from app.models.interview import Answer, Evaluation, InterviewQuestion, InterviewSession
from app.models.question_bank import QuestionBankItem
from app.models.user import User

__all__ = [
    "AgentDecisionRecord",
    "Answer",
    "CV",
    "CandidateProfile",
    "Evaluation",
    "ImprovementPlan",
    "InterviewQuestion",
    "InterviewSession",
    "QuestionBankItem",
    "RefreshToken",
    "User",
]
