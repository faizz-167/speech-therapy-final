from pydantic import BaseModel
from typing import Optional


class WeeklyPoint(BaseModel):
    week: str
    avg_score: float
    attempts: int


class TaskMetric(BaseModel):
    task_name: str
    overall_accuracy: float
    total_attempts: int
    current_level: Optional[str]


class ProgressResponse(BaseModel):
    total_attempts: int
    avg_final_score: float
    pass_rate: float
    weekly_trend: list[WeeklyPoint]
    task_metrics: list[TaskMetric]
    dominant_emotion: Optional[str]
