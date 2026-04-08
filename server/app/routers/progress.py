from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Annotated
from app.database import get_db
from app.auth import require_patient, require_therapist
from app.models.users import Patient, Therapist
from app.models.scoring import Session, SessionPromptAttempt, AttemptScoreDetail, PatientTaskProgress
from app.models.content import Prompt, Task, TaskLevel
from app.schemas.progress import ProgressResponse, WeeklyPoint, TaskMetric

router = APIRouter()


async def _build_progress(patient_id: str, db: AsyncSession) -> ProgressResponse:
    result = await db.execute(
        select(AttemptScoreDetail, SessionPromptAttempt, TaskLevel.task_id)
        .join(SessionPromptAttempt, AttemptScoreDetail.attempt_id == SessionPromptAttempt.attempt_id)
        .join(Prompt, SessionPromptAttempt.prompt_id == Prompt.prompt_id)
        .join(TaskLevel, Prompt.level_id == TaskLevel.level_id)
        .join(Session, SessionPromptAttempt.session_id == Session.session_id)
        .where(Session.patient_id == patient_id)
        .order_by(SessionPromptAttempt.created_at.desc())
    )
    rows = result.fetchall()

    if not rows:
        return ProgressResponse(
            total_attempts=0,
            avg_final_score=0,
            pass_rate=0,
            weekly_trend=[],
            task_metrics=[],
            dominant_emotion=None,
        )

    scores = [float(r.AttemptScoreDetail.final_score or 0) for r in rows]
    passes = sum(1 for r in rows if r.AttemptScoreDetail.pass_fail == "pass")
    emotions = [
        r.AttemptScoreDetail.dominant_emotion
        for r in rows
        if r.AttemptScoreDetail.dominant_emotion
    ]
    dominant_emotion = max(set(emotions), key=emotions.count) if emotions else None

    weekly: dict[str, list[float]] = {}
    for r in rows:
        created = r.AttemptScoreDetail.created_at
        week_key = created.strftime("%Y-W%U") if created else "unknown"
        weekly.setdefault(week_key, []).append(float(r.AttemptScoreDetail.final_score or 0))
    weekly_trend = [
        WeeklyPoint(week=k, avg_score=round(sum(v) / len(v), 2), attempts=len(v))
        for k, v in sorted(weekly.items())[-8:]
    ]

    task_rollups: dict[str, dict[str, float | int | str | None]] = {}
    for r in rows:
        task_id = r.task_id
        rollup = task_rollups.setdefault(
            task_id,
            {"total": 0, "passes": 0, "last_result": None},
        )
        rollup["total"] = int(rollup["total"] or 0) + 1
        if r.AttemptScoreDetail.pass_fail == "pass":
            rollup["passes"] = int(rollup["passes"] or 0) + 1
        if rollup["last_result"] is None:
            rollup["last_result"] = r.AttemptScoreDetail.pass_fail

    progress_result = await db.execute(
        select(PatientTaskProgress).where(PatientTaskProgress.patient_id == patient_id)
    )
    progress_rows = progress_result.scalars().all()
    task_metrics = []
    for pr in progress_rows:
        task = await db.get(Task, pr.task_id)
        level = await db.get(TaskLevel, pr.current_level_id) if pr.current_level_id else None
        rollup = task_rollups.get(pr.task_id, {})
        total = int(rollup.get("total", pr.total_attempts) or 0)
        passes_for_task = int(rollup.get("passes", 0) or 0)
        task_metrics.append(
            TaskMetric(
                task_id=pr.task_id,
                task_name=task.name if task else pr.task_id,
                overall_accuracy=float(pr.overall_accuracy or 0),
                total_attempts=pr.total_attempts,
                current_level=level.level_name if level else None,
                pass_rate=round((passes_for_task / total) * 100, 2) if total else 0,
                last_attempt_result=rollup.get("last_result"),
            )
        )

    return ProgressResponse(
        total_attempts=len(scores),
        avg_final_score=round(sum(scores) / len(scores), 2),
        pass_rate=round(passes / len(scores) * 100, 2),
        weekly_trend=weekly_trend,
        task_metrics=task_metrics,
        dominant_emotion=dominant_emotion,
    )


@router.get("/patient/progress", response_model=ProgressResponse)
async def patient_progress(
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    return await _build_progress(str(patient.patient_id), db)


@router.get("/therapist/patients/{patient_id}/progress", response_model=ProgressResponse)
async def therapist_patient_progress(
    patient_id: str,
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    patient = await db.get(Patient, patient_id)
    if not patient or str(patient.assigned_therapist_id) != str(therapist.therapist_id):
        raise HTTPException(404, "Patient not found")
    return await _build_progress(patient_id, db)
