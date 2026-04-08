from pydantic import BaseModel
from typing import Optional


class PromptOut(BaseModel):
    prompt_id: str
    prompt_type: str
    task_mode: str
    instruction: Optional[str]
    display_content: Optional[str]
    target_response: Optional[str]
    scenario_context: Optional[str]


class TaskAssignmentOut(BaseModel):
    assignment_id: str
    task_id: str
    task_name: str
    task_mode: str
    day_index: Optional[int]
    status: str
    current_level: Optional[str] = None
