import uuid
from typing import Annotated
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import String, cast, select
from sqlalchemy.orm import selectinload
import redis.asyncio as aioredis

from app.database import get_db
from app.auth import require_therapist
from app.config import settings
from app.models.users import Therapist, Patient
from app.models.plan import TherapyPlan, PlanTaskAssignment, PlanRevisionHistory
from app.models.content import Task, TaskDefectMapping, TaskLevel
from app.models.scoring import PatientTaskProgress, Session
from app.models.operations import PatientNotification
from app.schemas.plans import (
    GeneratePlanRequest, PlanOut, AssignmentOut, AddTaskRequest,
    UpdateAssignmentRequest, TaskForDefectOut, PlanRevisionEntryOut,
)
from app.services.plan_generator import generate_weekly_plan
from app.utils.plan_lock import clear_patient_plan_review_lock
from app.utils.session_notes import parse_session_notes, serialize_session_notes

router = APIRouter()
_PRIORITY_SHIFT_SENTINEL = 1000


async def _get_owned_plan(plan_id: str, therapist_id, db: AsyncSession) -> TherapyPlan:
    """Fetch a TherapyPlan owned by the given therapist, or raise 404."""
    result = await db.execute(
        select(TherapyPlan).where(
            TherapyPlan.plan_id == plan_id,
            TherapyPlan.therapist_id == therapist_id,
        )
    )
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Plan not found")
    return plan


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


async def _make_priority_slot(
    db: AsyncSession,
    plan_id: uuid.UUID,
    day_index: int,
    priority_order: int,
    exclude_assignment_id: uuid.UUID | None = None,
) -> None:
    stmt = (
        select(PlanTaskAssignment)
        .where(
            PlanTaskAssignment.plan_id == plan_id,
            PlanTaskAssignment.day_index == day_index,
            PlanTaskAssignment.priority_order >= priority_order,
        )
        .order_by(PlanTaskAssignment.priority_order.desc())
    )
    if exclude_assignment_id is not None:
        stmt = stmt.where(PlanTaskAssignment.assignment_id != exclude_assignment_id)

    result = await db.execute(stmt)
    assignments = result.scalars().all()
    if not assignments:
        return

    # Two-phase shift avoids transient uniqueness collisions on
    # (plan_id, day_index, priority_order) during flush.
    for assignment in assignments:
        assignment.priority_order = int(assignment.priority_order or 0) + _PRIORITY_SHIFT_SENTINEL
    await db.flush()

    for assignment in assignments:
        assignment.priority_order = int(assignment.priority_order or 0) - _PRIORITY_SHIFT_SENTINEL + 1
    await db.flush()


async def _compact_day_priorities(
    db: AsyncSession,
    plan_id: uuid.UUID,
    day_index: int,
) -> None:
    result = await db.execute(
        select(PlanTaskAssignment)
        .where(
            PlanTaskAssignment.plan_id == plan_id,
            PlanTaskAssignment.day_index == day_index,
        )
        .order_by(PlanTaskAssignment.priority_order.asc(), PlanTaskAssignment.assignment_id.asc())
    )
    assignments = result.scalars().all()

    # Two-phase rewrite avoids transient uniqueness collisions while
    # compacting priorities such as 0,2 -> 0,1.
    for assignment in assignments:
        assignment.priority_order = int(assignment.priority_order or 0) + _PRIORITY_SHIFT_SENTINEL
    await db.flush()

    for index, assignment in enumerate(assignments):
        assignment.priority_order = index
    await db.flush()


async def _notify_patient_plan_change(
    db: AsyncSession,
    plan: TherapyPlan,
    notification_type: str,
    message: str,
    *,
    assignment_id: uuid.UUID | None = None,
    action: str | None = None,
) -> None:
    db.add(
        PatientNotification(
            patient_id=plan.patient_id,
            plan_id=plan.plan_id,
            assignment_id=assignment_id,
            type=notification_type,
            message=message,
        )
    )
    await db.flush()

    payload = {
        "type": "plan_updated",
        "plan_id": str(plan.plan_id),
        "assignment_id": str(assignment_id) if assignment_id else None,
        "action": action or notification_type,
        "message": message,
    }
    r = aioredis.from_url(settings.redis_url)
    try:
        await r.publish(f"ws:patient:{plan.patient_id}", json.dumps(payload))
    finally:
        await r.aclose()


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


async def _get_current_therapist_plan(
    patient_id: str,
    therapist_id: uuid.UUID,
    db: AsyncSession,
) -> TherapyPlan | None:
    result = await db.execute(
        select(TherapyPlan)
        .where(
            TherapyPlan.patient_id == patient_id,
            TherapyPlan.therapist_id == therapist_id,
        )
        .options(selectinload(TherapyPlan.assignments))
        .order_by(TherapyPlan.created_at.desc())
    )
    plans = result.scalars().all()
    for plan in plans:
        if plan.status != "archived":
            return plan
    return plans[0] if plans else None


async def _resolve_default_task_level_name(task_id: str, db: AsyncSession) -> str | None:
    result = await db.execute(
        select(TaskLevel.level_name)
        .where(TaskLevel.task_id == task_id)
        .order_by(TaskLevel.difficulty_score.asc())
        .limit(1)
    )
    level_name = result.scalar_one_or_none()
    return level_name.lower() if isinstance(level_name, str) else level_name


async def _sync_patient_progress_to_assignment_level(
    patient_id: uuid.UUID,
    assignment: PlanTaskAssignment,
    db: AsyncSession,
) -> None:
    if not assignment.initial_level_name:
        return

    level_result = await db.execute(
        select(TaskLevel).where(
            TaskLevel.task_id == assignment.task_id,
            cast(TaskLevel.level_name, String) == assignment.initial_level_name,
        )
    )
    level = level_result.scalar_one_or_none()
    if not level:
        return

    progress_result = await db.execute(
        select(PatientTaskProgress).where(
            PatientTaskProgress.patient_id == patient_id,
            PatientTaskProgress.task_id == assignment.task_id,
        )
    )
    progress = progress_result.scalar_one_or_none()
    if progress:
        progress.current_level_id = level.level_id
        progress.level_locked_until = None
        progress.consecutive_passes = 0
        progress.consecutive_fails = 0
        progress.sessions_at_level = 0
    else:
        db.add(
            PatientTaskProgress(
                patient_id=patient_id,
                task_id=assignment.task_id,
                current_level_id=level.level_id,
                consecutive_passes=0,
                consecutive_fails=0,
                total_attempts=0,
                sessions_at_level=0,
            )
        )


async def _reset_assignment_sessions_for_level_change(
    plan: TherapyPlan,
    assignment: PlanTaskAssignment,
    db: AsyncSession,
) -> None:
    result = await db.execute(
        select(Session).where(
            Session.patient_id == plan.patient_id,
            Session.plan_id == plan.plan_id,
            Session.session_type == "therapy",
        )
    )
    for session in result.scalars().all():
        notes = parse_session_notes(session.session_notes)
        if notes.get("assignment_id") != str(assignment.assignment_id):
            continue
        if notes.get("completed"):
            continue
        notes["queue_items"] = []
        notes["queue_initialized"] = False
        notes["current_queue_level"] = assignment.initial_level_name
        notes["attempted_prompt_ids"] = []
        notes["completed_prompt_ids"] = []
        notes["passed_prompt_ids"] = []
        session.session_notes = serialize_session_notes(notes)


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
    plan = await _get_current_therapist_plan(patient_id, therapist.therapist_id, db)
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
    plan = await _get_owned_plan(plan_id, therapist.therapist_id, db)
    task = await db.get(Task, body.task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    default_level_name = await _resolve_default_task_level_name(body.task_id, db)
    target_priority = max(0, int(body.priority_order))
    await _make_priority_slot(db, plan.plan_id, body.day_index, target_priority)
    assignment = PlanTaskAssignment(
        assignment_id=uuid.uuid4(),
        plan_id=uuid.UUID(plan_id),
        task_id=body.task_id,
        therapist_id=therapist.therapist_id,
        day_index=body.day_index,
        priority_order=target_priority,
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
    if plan.status == "approved":
        await _notify_patient_plan_change(
            db,
            plan,
            "plan_updated",
            f"Your therapist added '{task.name}' to your plan for day {assignment.day_index + 1}.",
            assignment_id=assignment.assignment_id,
            action="add_task",
        )
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
    plan = await _get_owned_plan(plan_id, therapist.therapist_id, db)
    result = await db.execute(
        select(PlanTaskAssignment).where(
            PlanTaskAssignment.assignment_id == assignment_id,
            PlanTaskAssignment.plan_id == plan.plan_id,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(404, "Assignment not found")
    original_day_index = assignment.day_index
    original_priority = assignment.priority_order
    original_level_name = assignment.initial_level_name
    if body.day_index is not None:
        await _make_priority_slot(
            db,
            plan.plan_id,
            body.day_index,
            int(assignment.priority_order or 0),
            exclude_assignment_id=assignment.assignment_id,
        )
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
    elif body.day_index is not None:
        revision_old_value = {"day_index": original_day_index, "priority_order": original_priority}

    if plan.status == "approved" and body.initial_level_name is not None:
        await _sync_patient_progress_to_assignment_level(plan.patient_id, assignment, db)
        await _reset_assignment_sessions_for_level_change(plan, assignment, db)

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
    task = await db.get(Task, assignment.task_id)
    if plan.status == "approved":
        if revision_action == "update_level":
            await _notify_patient_plan_change(
                db,
                plan,
                "plan_updated",
                (
                    f"Your therapist updated '{task.name if task else assignment.task_id}' "
                    f"from {original_level_name or 'beginner'} to {assignment.initial_level_name or 'beginner'}."
                ),
                assignment_id=assignment.assignment_id,
                action="update_level",
            )
        elif body.day_index is not None:
            await _notify_patient_plan_change(
                db,
                plan,
                "plan_updated",
                (
                    f"Your therapist rescheduled '{task.name if task else assignment.task_id}' "
                    f"from day {int(original_day_index or 0) + 1} to day {int(assignment.day_index or 0) + 1}."
                ),
                assignment_id=assignment.assignment_id,
                action="reorder",
            )
    await db.commit()
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
    plan = await _get_owned_plan(plan_id, therapist.therapist_id, db)
    result = await db.execute(
        select(PlanTaskAssignment).where(
            PlanTaskAssignment.assignment_id == assignment_id,
            PlanTaskAssignment.plan_id == plan.plan_id,
        )
    )
    assignment = result.scalar_one_or_none()
    if not assignment:
        raise HTTPException(404, "Assignment not found")
    old_day_index = assignment.day_index
    task = await db.get(Task, assignment.task_id)
    old_val = {
        "task_id": str(assignment.task_id),
        "day_index": assignment.day_index,
        "priority_order": assignment.priority_order,
    }
    history_result = await db.execute(
        select(PlanRevisionHistory).where(
            PlanRevisionHistory.assignment_id == assignment.assignment_id,
        )
    )
    for revision_entry in history_result.scalars().all():
        revision_entry.assignment_id = None

    patient_notification_result = await db.execute(
        select(PatientNotification).where(
            PatientNotification.assignment_id == assignment.assignment_id,
        )
    )
    for notification in patient_notification_result.scalars().all():
        notification.assignment_id = None

    await db.delete(assignment)
    await db.flush()
    if old_day_index is not None:
        await _compact_day_priorities(db, plan.plan_id, old_day_index)

    revision = PlanRevisionHistory(
        plan_id=plan.plan_id,
        therapist_id=therapist.therapist_id,
        action="remove_task",
        old_value=old_val,
    )
    db.add(revision)
    if plan.status == "approved":
        await _notify_patient_plan_change(
            db,
            plan,
            "plan_updated",
            f"Your therapist removed '{task.name if task else assignment.task_id}' from your plan.",
            action="remove_task",
        )
    await db.commit()
    return {"message": "Deleted"}


@router.post("/{plan_id}/approve")
async def approve_plan(
    plan_id: str,
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    plan = await _get_owned_plan(plan_id, therapist.therapist_id, db)
    archive_result = await db.execute(
        select(TherapyPlan).where(
            TherapyPlan.patient_id == plan.patient_id,
            TherapyPlan.therapist_id == therapist.therapist_id,
            TherapyPlan.plan_id != plan.plan_id,
            TherapyPlan.status == "approved",
        )
    )
    for prior_plan in archive_result.scalars().all():
        prior_plan.status = "archived"
    plan.status = "approved"
    await clear_patient_plan_review_lock(plan.patient_id, db)
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
    await db.flush()
    r = aioredis.from_url(settings.redis_url)
    try:
        await r.publish(
            f"ws:patient:{plan.patient_id}",
            json.dumps(
                {
                    "type": "plan_updated",
                    "plan_id": str(plan.plan_id),
                    "assignment_id": None,
                    "action": "approve",
                    "message": f"Your therapist approved the plan '{plan.plan_name}'. Today's tasks are ready.",
                }
            ),
        )
    finally:
        await r.aclose()
    await db.commit()
    return {"message": "Plan approved"}


@router.post("/{plan_id}/reject")
async def reject_plan(
    plan_id: str,
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    plan = await _get_owned_plan(plan_id, therapist.therapist_id, db)
    if plan.status == "approved":
        raise HTTPException(400, "Approved plans cannot be rejected")

    plan.status = "archived"
    db.add(
        PlanRevisionHistory(
            plan_id=plan.plan_id,
            therapist_id=therapist.therapist_id,
            action="reject",
            note="Plan rejected by therapist.",
        )
    )
    await db.commit()
    return {"message": "Plan rejected. Patient remains locked until a plan is approved."}


@router.get("/{plan_id}/revision-history", response_model=list[PlanRevisionEntryOut])
async def get_revision_history(
    plan_id: str,
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    plan = await _get_owned_plan(plan_id, therapist.therapist_id, db)
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
    plan = await _get_owned_plan(plan_id, therapist.therapist_id, db)
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
