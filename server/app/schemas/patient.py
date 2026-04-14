from datetime import date
from pydantic import BaseModel
from typing import Optional


class AssignedDefectOut(BaseModel):
    defect_id: str
    name: str
    category: str


class PatientProfileOut(BaseModel):
    patient_id: str
    full_name: str
    email: str
    date_of_birth: date
    gender: Optional[str]
    status: str
    current_streak: int
    best_streak: int
    assigned_defects: list[AssignedDefectOut]
    therapist_name: Optional[str]
    primary_diagnosis: Optional[str]
    member_since: Optional[str]


class PromptOut(BaseModel):
    prompt_id: str
    prompt_type: str
    task_mode: str
    instruction: Optional[str]
    display_content: Optional[str]
    target_response: Optional[str]
    scenario_context: Optional[str]


class TaskExerciseStateOut(BaseModel):
    session_id: str
    current_level: str
    total_prompts: int
    completed_prompts: int
    task_complete: bool
    current_prompt: Optional[PromptOut]
    escalated: bool = False
    escalation_message: Optional[str] = None


class PatientNotificationOut(BaseModel):
    id: str
    notification_type: str
    message: str
    is_read: bool
    created_at: str
    plan_id: Optional[str] = None
    assignment_id: Optional[str] = None


class TaskAssignmentOut(BaseModel):
    assignment_id: str
    task_id: str
    task_name: str
    task_mode: str
    day_index: Optional[int]
    status: str
    priority_order: Optional[int] = None
    current_level: Optional[str] = None


class TodayTasksResponse(BaseModel):
    assignments: list[TaskAssignmentOut]
    any_escalated: bool
