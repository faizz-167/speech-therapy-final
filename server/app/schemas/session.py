from pydantic import BaseModel
from typing import Optional


class StartSessionRequest(BaseModel):
    plan_id: Optional[str] = None
    assignment_id: Optional[str] = None


class AttemptStatusResponse(BaseModel):
    attempt_id: str
    result: Optional[str]
    score: Optional[dict] = None
