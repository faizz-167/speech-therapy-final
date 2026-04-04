import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.auth import require_therapist
from app.models.users import Therapist, Patient
from app.models.plan import TherapyPlan, PlanTaskAssignment
from app.models.content import Task, TaskDefectMapping
from app.schemas.plans import (
    GeneratePlanRequest, PlanOut, AssignmentOut, AddTaskRequest,
    UpdateAssignmentRequest, TaskForDefectOut,
)
from app.services.plan_generator import generate_weekly_plan

router = APIRouter()


async def _plan_to_out(plan: TherapyPlan, db: AsyncSession) -> PlanOut:
    task_ids = [a.task_id for a in plan.assignments]
    tasks_by_id: dict[str, Task] = {}
    if task_ids:
        task_result = await db.execute(select(Task).where(Task.task_id.in_(task_ids)))
        tasks_by_id = {task.task_id: task for task in task_result.scalars().all()}

    assignments = []
    for a in plan.assignments:
        task = tasks_by_id.get(a.task_id)
        assignments.append(AssignmentOut(
            assignment_id=str(a.assignment_id),
            task_id=a.task_id,
            task_name=task.name if task else a.task_id,
            task_mode=task.task_mode if task else "",
            day_index=a.day_index,
            status=a.status,
            priority_order=a.priority_order,
        ))
    return PlanOut(
        plan_id=str(plan.plan_id),
        plan_name=plan.plan_name,
        start_date=plan.start_date,
        end_date=plan.end_date,
        status=plan.status,
        goals=plan.goals,
        assignments=assignments,
    )


async def _get_plan_with_assignments(stmt, db: AsyncSession) -> TherapyPlan | None:
    result = await db.execute(stmt.options(selectinload(TherapyPlan.assignments)))
    return result.scalar_one_or_none()


@router.post("/generate", response_model=PlanOut)
async def generate_plan(
    body: GeneratePlanRequest,
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Patient).where(
            Patient.patient_id == body.patient_id,
            Patient.assigned_therapist_id == therapist.therapist_id,
        )
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(404, "Patient not found")
    try:
        plan = await generate_weekly_plan(patient, therapist, body.baseline_level, db)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    plan = await _get_plan_with_assignments(
        select(TherapyPlan).where(TherapyPlan.plan_id == plan.plan_id),
        db,
    )
    if not plan:
        raise HTTPException(404, "Plan not found after creation")
    return await _plan_to_out(plan, db)


@router.get("/patient/{patient_id}/current", response_model=PlanOut | None)
async def get_patient_plan(
    patient_id: str,
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    plan = await _get_plan_with_assignments(
        select(TherapyPlan).where(
            TherapyPlan.patient_id == patient_id,
            TherapyPlan.therapist_id == therapist.therapist_id,
        ).order_by(TherapyPlan.created_at.desc())
        .limit(1),
        db,
    )
    if not plan:
        return None
    return await _plan_to_out(plan, db)


@router.get("/{plan_id}", response_model=PlanOut)
async def get_plan(
    plan_id: str,
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    plan = await _get_plan_with_assignments(
        select(TherapyPlan).where(
            TherapyPlan.plan_id == plan_id,
            TherapyPlan.therapist_id == therapist.therapist_id,
        ),
        db,
    )
    if not plan:
        raise HTTPException(404, "Plan not found")
    return await _plan_to_out(plan, db)


@router.post("/{plan_id}/tasks", response_model=AssignmentOut)
async def add_task(
    plan_id: str,
    body: AddTaskRequest,
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TherapyPlan).where(
            TherapyPlan.plan_id == plan_id,
            TherapyPlan.therapist_id == therapist.therapist_id,
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Plan not found")
    task = await db.get(Task, body.task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    assignment = PlanTaskAssignment(
        assignment_id=uuid.uuid4(),
        plan_id=uuid.UUID(plan_id),
        task_id=body.task_id,
        therapist_id=therapist.therapist_id,
        day_index=body.day_index,
        priority_order=body.priority_order,
        status="pending",
    )
    db.add(assignment)
    await db.commit()
    return AssignmentOut(
        assignment_id=str(assignment.assignment_id),
        task_id=task.task_id,
        task_name=task.name,
        task_mode=task.task_mode,
        day_index=assignment.day_index,
        status=assignment.status,
        priority_order=assignment.priority_order,
    )


@router.patch("/{plan_id}/tasks/{assignment_id}", response_model=AssignmentOut)
async def update_assignment(
    plan_id: str,
    assignment_id: str,
    body: UpdateAssignmentRequest,
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    plan_result = await db.execute(
        select(TherapyPlan).where(
            TherapyPlan.plan_id == plan_id,
            TherapyPlan.therapist_id == therapist.therapist_id,
        )
    )
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Plan not found")
    result = await db.execute(
        select(PlanTaskAssignment).where(
            PlanTaskAssignment.assignment_id == assignment_id,
            PlanTaskAssignment.plan_id == plan.plan_id,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(404, "Assignment not found")
    if body.day_index is not None:
        assignment.day_index = body.day_index
    if body.status is not None:
        assignment.status = body.status
    await db.commit()
    task = await db.get(Task, assignment.task_id)
    return AssignmentOut(
        assignment_id=str(assignment.assignment_id),
        task_id=assignment.task_id,
        task_name=task.name if task else assignment.task_id,
        task_mode=task.task_mode if task else "",
        day_index=assignment.day_index,
        status=assignment.status,
        priority_order=assignment.priority_order,
    )


@router.delete("/{plan_id}/tasks/{assignment_id}")
async def delete_assignment(
    plan_id: str,
    assignment_id: str,
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    plan_result = await db.execute(
        select(TherapyPlan).where(
            TherapyPlan.plan_id == plan_id,
            TherapyPlan.therapist_id == therapist.therapist_id,
        )
    )
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Plan not found")
    result = await db.execute(
        select(PlanTaskAssignment).where(
            PlanTaskAssignment.assignment_id == assignment_id,
            PlanTaskAssignment.plan_id == plan.plan_id,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(404, "Assignment not found")
    await db.delete(assignment)
    await db.commit()
    return {"message": "Deleted"}


@router.post("/{plan_id}/approve")
async def approve_plan(
    plan_id: str,
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TherapyPlan).where(
            TherapyPlan.plan_id == plan_id,
            TherapyPlan.therapist_id == therapist.therapist_id,
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Plan not found")
    plan.status = "approved"
    await db.commit()
    return {"message": "Plan approved"}


@router.get("/{plan_id}/tasks-for-defects", response_model=list[TaskForDefectOut])
async def tasks_for_defects(
    plan_id: str,
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    plan_result = await db.execute(
        select(TherapyPlan).where(
            TherapyPlan.plan_id == plan_id,
            TherapyPlan.therapist_id == therapist.therapist_id,
        )
    )
    plan = plan_result.scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Plan not found")
    patient = await db.get(Patient, plan.patient_id)
    if not patient:
        raise HTTPException(404, "Patient not found")
    defect_ids = (patient.pre_assigned_defect_ids or {}).get("defect_ids", [])
    mapping_result = await db.execute(
        select(TaskDefectMapping.task_id)
        .where(TaskDefectMapping.defect_id.in_(defect_ids))
        .distinct()
    )
    task_ids = [row[0] for row in mapping_result.fetchall()]
    tasks_result = await db.execute(select(Task).where(Task.task_id.in_(task_ids)))
    tasks = tasks_result.scalars().all()
    return [
        TaskForDefectOut(task_id=t.task_id, name=t.name, task_mode=t.task_mode, type=t.type)
        for t in tasks
    ]
