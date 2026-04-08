from pydantic import BaseModel
from typing import Optional


class BaselineItemOut(BaseModel):
    item_id: str
    task_name: Optional[str]
    instruction: Optional[str]
    display_content: Optional[str]
    expected_output: Optional[str]
    response_type: Optional[str]
    target_phoneme: Optional[str]
    formula_weights: Optional[dict]
    fusion_weights: Optional[dict]
    wpm_range: Optional[dict]


class BaselineSectionOut(BaseModel):
    section_id: str
    section_name: str
    instructions: Optional[str]
    order_index: int
    items: list[BaselineItemOut]


class BaselineAssessmentOut(BaseModel):
    baseline_id: str
    name: str
    domain: str
    sections: list[BaselineSectionOut]


class ItemScoreSubmit(BaseModel):
    item_id: str
    score: float


class BaselineSubmitRequest(BaseModel):
    baseline_id: str
    item_scores: list[ItemScoreSubmit]


class BaselineResultOut(BaseModel):
    result_id: str
    baseline_name: str
    raw_score: int
    level: str
    assessed_on: str


class BaselineItemDetailOut(BaseModel):
    item_id: str
    prompt_text: Optional[str]
    transcript: Optional[str]
    phoneme_accuracy: Optional[float]
    fluency_score: Optional[float]
    final_score: float
    pass_fail: bool
    created_at: str
