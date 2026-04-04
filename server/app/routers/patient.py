from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Annotated
from datetime import date
from app.database import get_db
from app.auth import require_patient
from app.models.users import Patient
from app.models.plan import TherapyPlan, PlanTaskAssignment
from app.models.content import Task, TaskLevel, Prompt
from app.schemas.patient import TaskAssignmentOut, PromptOut

router = APIRouter()


@router.get("/profile")
async def get_profile(patient: Annotated[Patient, Depends(require_patient)]):
    return {
        "patient_id": str(patient.patient_id),
        "full_name": patient.full_name,
        "email": patient.email,
        "date_of_birth": patient.date_of_birth,
        "gender": patient.gender,
        "status": patient.status.value,
        "current_streak": patient.current_streak,
    }


@router.get("/home")
async def patient_home(
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    from app.models.baseline import PatientBaselineResult
    baseline_result = await db.execute(
        select(PatientBaselineResult).where(PatientBaselineResult.patient_id == patient.patient_id)
    )
    has_baseline = baseline_result.scalar_one_or_none() is not None
    return {"has_baseline": has_baseline, "full_name": patient.full_name}


@router.get("/tasks", response_model=list[TaskAssignmentOut])
async def get_today_tasks(
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    plan_result = await db.execute(
        select(TherapyPlan).where(
            TherapyPlan.patient_id == patient.patient_id,
            TherapyPlan.status == "approved",
        ).order_by(TherapyPlan.created_at.desc())
    )
    plan = plan_result.scalar_one_or_none()
    if not plan:
        return []
    today_idx = date.today().weekday()
    assignment_result = await db.execute(
        select(PlanTaskAssignment).where(
            PlanTaskAssignment.plan_id == plan.plan_id,
            PlanTaskAssignment.day_index == today_idx,
        )
    )
    assignments = assignment_result.scalars().all()
    out = []
    for a in assignments:
        task = await db.get(Task, a.task_id)
        out.append(TaskAssignmentOut(
            assignment_id=str(a.assignment_id),
            task_id=a.task_id,
            task_name=task.name if task else a.task_id,
            task_mode=task.task_mode if task else "",
            day_index=a.day_index,
            status=a.status,
        ))
    return out


@router.get("/tasks/{assignment_id}/prompts", response_model=list[PromptOut])
async def get_prompts(
    assignment_id: str,
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    assignment = await db.get(PlanTaskAssignment, assignment_id)
    if not assignment:
        raise HTTPException(404, "Assignment not found")
    task = await db.get(Task, assignment.task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    level_result = await db.execute(
        select(TaskLevel).where(
            TaskLevel.task_id == task.task_id,
            TaskLevel.level_name == "easy",
        )
    )
    level = level_result.scalar_one_or_none()
    if not level:
        return []
    prompts_result = await db.execute(
        select(Prompt).where(Prompt.level_id == level.level_id)
    )
    prompts = prompts_result.scalars().all()
    return [
        PromptOut(
            prompt_id=p.prompt_id,
            prompt_type=p.prompt_type,
            task_mode=p.task_mode,
            instruction=p.instruction,
            display_content=p.display_content,
            target_response=p.target_response,
            scenario_context=p.scenario_context,
        )
        for p in prompts
    ]


@router.post("/tasks/{assignment_id}/complete")
async def complete_task(
    assignment_id: str,
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    assignment = await db.get(PlanTaskAssignment, assignment_id)
    if not assignment:
        raise HTTPException(404, "Assignment not found")
    assignment.status = "completed"
    await db.commit()
    return {"message": "Task marked complete"}
