from pydantic import BaseModel
from typing import Optional


class GeneratePlanRequest(BaseModel):
    patient_id: str
    baseline_level: str = "easy"


class AssignmentOut(BaseModel):
    assignment_id: str
    task_id: str
    task_name: str
    task_mode: str
    day_index: int | None
    status: str
    priority_order: int | None


class PlanOut(BaseModel):
    plan_id: str
    plan_name: str
    start_date: str | None
    end_date: str | None
    status: str
    goals: str | None
    assignments: list[AssignmentOut]


class AddTaskRequest(BaseModel):
    task_id: str
    day_index: int
    priority_order: int = 0


class UpdateAssignmentRequest(BaseModel):
    day_index: int | None = None
    status: str | None = None


class TaskForDefectOut(BaseModel):
    task_id: str
    name: str
    task_mode: str
    type: str


class PlanRevisionEntryOut(BaseModel):
    id: str
    action: str
    actor_role: str
    change_summary: Optional[str]
    created_at: str
