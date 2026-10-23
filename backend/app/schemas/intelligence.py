import uuid

from pydantic import BaseModel

from app.schemas.common import Timestamp


class ImprovementPlanOut(BaseModel):
    id: uuid.UUID
    interview_id: uuid.UUID
    target_role: str
    plan_version: str
    created_at: Timestamp
    updated_at: Timestamp
    plan: dict  # structure documented in app/intelligence/improvement.py
