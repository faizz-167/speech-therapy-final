import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import String, cast, select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.auth import require_therapist
from app.models.users import Therapist, Patient
from app.models.plan import TherapyPlan, PlanTaskAssignment, PlanRevisionHistory
from app.models.content import Task, TaskDefectMapping, TaskLevel
from app.models.operations import PatientNotification
from app.schemas.plans import (
    GeneratePlanRequest, PlanOut, AssignmentOut, AddTaskRequest,
    UpdateAssignmentRequest, TaskForDefectOut, PlanRevisionEntryOut,
)
from app.services.plan_generator import generate_weekly_plan

router = APIRouter()


def _build_revision_summary(entry: PlanRevisionHistory) -> str | None:
    if entry.note:
        return entry.note
    if entry.action == "update_level" and entry.old_value and entry.new_value:
        return (
            f"Changed level from {entry.old_value.get('initial_level_name')} "
            f"to {entry.new_value.get('initial_level_name')}"
        )
    if entry.action == "add_task" and entry.new_value:
        return f"Added task {entry.new_value.get('task_id')} to day {entry.new_value.get('day_index')}"
    if entry.action == "reorder" and entry.new_value:
        return (
            f"Moved assignment to day {entry.new_value.get('day_index')} "
            f"with priority {entry.new_value.get('priority_order')}"
        )
    if entry.action == "remove_task" and entry.old_value:
        return f"Removed task {entry.old_value.get('task_id')} from day {entry.old_value.get('day_index')}"
    return None


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
            initial_level_name=a.initial_level_name,
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


async def _resolve_default_task_level_name(task_id: str, db: AsyncSession) -> str | None:
    result = await db.execute(
        select(TaskLevel.level_name)
        .where(TaskLevel.task_id == task_id)
        .order_by(TaskLevel.difficulty_score.asc())
        .limit(1)
    )
    level_name = result.scalar_one_or_none()
    return level_name.lower() if isinstance(level_name, str) else level_name


async def _validate_task_level_name(task_id: str, level_name: str, db: AsyncSession) -> str:
    normalized = (level_name or "").strip().lower()
    if not normalized:
        raise HTTPException(400, "Level is required")

    result = await db.execute(
        select(TaskLevel.level_name).where(
            TaskLevel.task_id == task_id,
            cast(TaskLevel.level_name, String) == normalized,
        )
    )
    resolved = result.scalar_one_or_none()
    if not resolved:
        raise HTTPException(400, f"Level '{normalized}' is not available for this task")
    return str(resolved).lower()


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
    default_level_name = await _resolve_default_task_level_name(body.task_id, db)
    assignment = PlanTaskAssignment(
        assignment_id=uuid.uuid4(),
        plan_id=uuid.UUID(plan_id),
        task_id=body.task_id,
        therapist_id=therapist.therapist_id,
        day_index=body.day_index,
        priority_order=body.priority_order,
        status="pending",
        initial_level_name=default_level_name,
    )
    db.add(assignment)
    await db.commit()
    revision = PlanRevisionHistory(
        plan_id=plan.plan_id,
        therapist_id=therapist.therapist_id,
        action="add_task",
        assignment_id=assignment.assignment_id,
        new_value={"task_id": str(assignment.task_id), "day_index": assignment.day_index},
    )
    db.add(revision)
    await db.commit()
    return AssignmentOut(
        assignment_id=str(assignment.assignment_id),
        task_id=task.task_id,
        task_name=task.name,
        task_mode=task.task_mode,
        day_index=assignment.day_index,
        status=assignment.status,
        priority_order=assignment.priority_order,
        initial_level_name=assignment.initial_level_name,
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
    revision_action = "reorder"
    revision_old_value = None
    revision_new_value = {"day_index": assignment.day_index, "priority_order": assignment.priority_order}
    if body.initial_level_name is not None:
        validated_level_name = await _validate_task_level_name(assignment.task_id, body.initial_level_name, db)
        revision_action = "update_level"
        revision_old_value = {"initial_level_name": assignment.initial_level_name}
        assignment.initial_level_name = validated_level_name
        revision_new_value = {"initial_level_name": assignment.initial_level_name}
    await db.commit()
    revision = PlanRevisionHistory(
        plan_id=plan.plan_id,
        therapist_id=therapist.therapist_id,
        action=revision_action,
        assignment_id=assignment.assignment_id,
        old_value=revision_old_value,
        new_value=revision_new_value,
    )
    db.add(revision)
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
        initial_level_name=assignment.initial_level_name,
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
    old_val = {"task_id": str(assignment.task_id), "day_index": assignment.day_index}
    await db.delete(assignment)
    await db.commit()
    revision = PlanRevisionHistory(
        plan_id=plan.plan_id,
        therapist_id=therapist.therapist_id,
        action="remove_task",
        old_value=old_val,
    )
    db.add(revision)
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
    revision = PlanRevisionHistory(
        plan_id=plan.plan_id,
        therapist_id=therapist.therapist_id,
        action="approve",
        note="Plan approved by therapist.",
    )
    db.add(revision)
    db.add(PatientNotification(
        patient_id=plan.patient_id,
        plan_id=plan.plan_id,
        type="plan_approved",
        message=f"Your therapist approved the plan '{plan.plan_name}'. Today's tasks are ready.",
    ))
    await db.commit()
    return {"message": "Plan approved"}


@router.get("/{plan_id}/revision-history", response_model=list[PlanRevisionEntryOut])
async def get_revision_history(
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
    history_result = await db.execute(
        select(PlanRevisionHistory)
        .where(PlanRevisionHistory.plan_id == plan.plan_id)
        .order_by(PlanRevisionHistory.created_at.asc())
    )
    entries = history_result.scalars().all()
    return [
        PlanRevisionEntryOut(
            id=str(e.revision_id),
            action=e.action,
            actor_role="therapist",
            change_summary=_build_revision_summary(e),
            created_at=e.created_at.isoformat(),
        )
        for e in entries
    ]


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
