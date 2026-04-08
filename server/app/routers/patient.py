import json
import uuid
from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import String, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_patient
from app.database import get_db
from app.models.baseline import PatientBaselineResult
from app.models.content import Defect, Prompt, Task, TaskLevel
from app.models.operations import PatientNotification
from app.models.plan import PlanTaskAssignment, TherapyPlan
from app.models.scoring import PatientTaskProgress, Session
from app.models.users import Patient, Therapist
from app.schemas.patient import (
    PatientNotificationOut,
    PatientProfileOut,
    PromptOut,
    TaskAssignmentOut,
    TaskExerciseStateOut,
)

router = APIRouter()


def _normalize_task_level_name(level: str | None) -> str:
    normalized = (level or "").strip().lower()
    return {
        "easy": "beginner",
        "medium": "intermediate",
        "advanced": "advanced",
        "beginner": "beginner",
        "elementary": "elementary",
        "intermediate": "intermediate",
        "expert": "expert",
    }.get(normalized, "beginner")


def _default_session_notes(
    assignment_id: str | None = None,
    task_id: str | None = None,
) -> dict:
    return {
        "assignment_id": assignment_id,
        "task_id": task_id,
        "completed_prompt_ids": [],
        "passed_prompt_ids": [],
        "completed": False,
        "completion_status": None,
    }


def _parse_session_notes(notes: str | None) -> dict:
    data = _default_session_notes()
    if not notes:
        return data
    try:
        parsed = json.loads(notes)
    except (TypeError, ValueError):
        return data
    if isinstance(parsed, dict):
        data.update(parsed)
    completed_prompt_ids = data.get("completed_prompt_ids") or []
    passed_prompt_ids = data.get("passed_prompt_ids") or []
    data["completed_prompt_ids"] = [
        str(prompt_id) for prompt_id in completed_prompt_ids if prompt_id
    ]
    data["passed_prompt_ids"] = [
        str(prompt_id) for prompt_id in passed_prompt_ids if prompt_id
    ]
    data["completed"] = bool(data.get("completed"))
    return data


def _serialize_session_notes(notes: dict) -> str:
    normalized = _default_session_notes(
        assignment_id=notes.get("assignment_id"),
        task_id=notes.get("task_id"),
    )
    normalized["completed_prompt_ids"] = list(
        dict.fromkeys(str(prompt_id) for prompt_id in (notes.get("completed_prompt_ids") or []) if prompt_id)
    )
    normalized["passed_prompt_ids"] = list(
        dict.fromkeys(str(prompt_id) for prompt_id in (notes.get("passed_prompt_ids") or []) if prompt_id)
    )
    normalized["completed"] = bool(notes.get("completed"))
    normalized["completion_status"] = notes.get("completion_status")
    return json.dumps(normalized)


def _prompt_to_out(prompt: Prompt) -> PromptOut:
    return PromptOut(
        prompt_id=prompt.prompt_id,
        prompt_type=prompt.prompt_type,
        task_mode=prompt.task_mode,
        instruction=prompt.instruction,
        display_content=prompt.display_content,
        target_response=prompt.target_response,
        scenario_context=prompt.scenario_context,
    )


async def _get_current_plan(
    patient_id: uuid.UUID,
    db: AsyncSession,
) -> TherapyPlan | None:
    result = await db.execute(
        select(TherapyPlan)
        .where(
            TherapyPlan.patient_id == patient_id,
            TherapyPlan.status == "approved",
        )
        .order_by(TherapyPlan.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _resolve_task_level_name(
    patient: Patient,
    task_id: str,
    db: AsyncSession,
) -> str:
    progress_result = await db.execute(
        select(PatientTaskProgress).where(
            PatientTaskProgress.patient_id == patient.patient_id,
            PatientTaskProgress.task_id == task_id,
        )
    )
    progress = progress_result.scalar_one_or_none()
    if progress and progress.current_level_id:
        level = await db.get(TaskLevel, progress.current_level_id)
        if level:
            return level.level_name

    baseline_result = await db.execute(
        select(PatientBaselineResult)
        .where(PatientBaselineResult.patient_id == patient.patient_id)
        .order_by(PatientBaselineResult.assessed_on.desc())
    )
    baseline = baseline_result.scalars().first()
    if baseline and baseline.severity_rating:
        return _normalize_task_level_name(baseline.severity_rating)
    return "beginner"


async def _load_level_prompts(
    task_id: str,
    target_level_name: str,
    db: AsyncSession,
) -> tuple[TaskLevel | None, list[Prompt]]:
    level_result = await db.execute(
        select(TaskLevel).where(
            TaskLevel.task_id == task_id,
            cast(TaskLevel.level_name, String) == target_level_name,
        )
    )
    level = level_result.scalar_one_or_none()
    if not level:
        fallback_result = await db.execute(
            select(TaskLevel).where(
                TaskLevel.task_id == task_id,
                cast(TaskLevel.level_name, String) == "beginner",
            )
        )
        level = fallback_result.scalar_one_or_none()
    if not level:
        return None, []
    prompts_result = await db.execute(
        select(Prompt).where(Prompt.level_id == level.level_id)
    )
    return level, prompts_result.scalars().all()


async def _get_assignment(
    assignment_id: str,
    patient: Patient,
    db: AsyncSession,
) -> tuple[PlanTaskAssignment, TherapyPlan, Task]:
    assignment = await db.get(PlanTaskAssignment, assignment_id)
    if not assignment:
        raise HTTPException(404, "Assignment not found")
    plan = await db.get(TherapyPlan, assignment.plan_id)
    if not plan or plan.patient_id != patient.patient_id:
        raise HTTPException(404, "Assignment not found")
    if plan.status != "approved":
        raise HTTPException(403, "Plan is not approved")
    task = await db.get(Task, assignment.task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    return assignment, plan, task


async def _find_active_assignment_session(
    patient_id: uuid.UUID,
    plan_id: uuid.UUID,
    assignment_id: str,
    db: AsyncSession,
) -> Session | None:
    result = await db.execute(
        select(Session)
        .where(
            Session.patient_id == patient_id,
            Session.plan_id == plan_id,
            Session.session_type == "therapy",
        )
        .order_by(Session.session_date.desc())
    )
    for session in result.scalars().all():
        notes = _parse_session_notes(session.session_notes)
        if notes.get("assignment_id") == assignment_id and not notes.get("completed"):
            return session
    return None


async def _create_assignment_session(
    patient: Patient,
    plan: TherapyPlan,
    assignment: PlanTaskAssignment,
    db: AsyncSession,
) -> Session:
    session = Session(
        session_id=uuid.uuid4(),
        patient_id=patient.patient_id,
        therapist_id=patient.assigned_therapist_id,
        plan_id=plan.plan_id,
        session_type="therapy",
        session_notes=_serialize_session_notes(
            _default_session_notes(
                assignment_id=str(assignment.assignment_id),
                task_id=assignment.task_id,
            )
        ),
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def _get_or_create_assignment_session(
    patient: Patient,
    plan: TherapyPlan,
    assignment: PlanTaskAssignment,
    db: AsyncSession,
) -> Session:
    active_session = await _find_active_assignment_session(
        patient.patient_id,
        plan.plan_id,
        str(assignment.assignment_id),
        db,
    )
    if active_session:
        return active_session
    return await _create_assignment_session(patient, plan, assignment, db)


async def _build_task_state(
    patient: Patient,
    assignment: PlanTaskAssignment,
    plan: TherapyPlan,
    task: Task,
    db: AsyncSession,
) -> TaskExerciseStateOut:
    session = await _get_or_create_assignment_session(patient, plan, assignment, db)
    notes = _parse_session_notes(session.session_notes)
    target_level_name = await _resolve_task_level_name(patient, task.task_id, db)
    level, prompts = await _load_level_prompts(task.task_id, target_level_name, db)
    current_level_name = level.level_name if level else "beginner"

    completed_prompt_ids = set(notes.get("completed_prompt_ids") or [])
    passed_prompt_ids = set(notes.get("passed_prompt_ids") or [])
    remaining_prompts = [prompt for prompt in prompts if prompt.prompt_id not in completed_prompt_ids]
    current_prompt = remaining_prompts[0] if remaining_prompts else None
    prompt_ids = {prompt.prompt_id for prompt in prompts}
    all_passed = bool(prompts) and prompt_ids.issubset(passed_prompt_ids)

    return TaskExerciseStateOut(
        session_id=str(session.session_id),
        current_level=current_level_name,
        total_prompts=len(prompts),
        completed_prompts=len(prompts) - len(remaining_prompts),
        task_complete=current_prompt is None and all_passed,
        current_prompt=_prompt_to_out(current_prompt) if current_prompt else None,
    )


async def _create_patient_notification(
    patient_id: uuid.UUID,
    notification_type: str,
    message: str,
    db: AsyncSession,
    plan_id: uuid.UUID | None = None,
    assignment_id: uuid.UUID | None = None,
) -> None:
    notification = PatientNotification(
        patient_id=patient_id,
        type=notification_type,
        plan_id=plan_id,
        assignment_id=assignment_id,
        message=message,
    )
    db.add(notification)


async def _ensure_patient_notifications(
    patient: Patient,
    db: AsyncSession,
) -> None:
    plan = await _get_current_plan(patient.patient_id, db)
    if not plan:
        await db.commit()
        return

    today = date.today()
    today_idx = today.weekday()
    assignment_result = await db.execute(
        select(PlanTaskAssignment).where(
            PlanTaskAssignment.plan_id == plan.plan_id,
            PlanTaskAssignment.day_index == today_idx,
        )
    )
    todays_assignments = assignment_result.scalars().all()
    if not todays_assignments:
        await db.commit()
        return

    existing_result = await db.execute(
        select(PatientNotification).where(
            PatientNotification.patient_id == patient.patient_id,
        )
    )
    existing = existing_result.scalars().all()

    def has_today_notification(notification_type: str) -> bool:
        return any(
            note.type == notification_type and note.created_at.date() == today
            for note in existing
        )

    pending_assignments = [assignment for assignment in todays_assignments if assignment.status != "completed"]
    if not has_today_notification("daily_task_reminder"):
        await _create_patient_notification(
            patient.patient_id,
            "daily_task_reminder",
            f"You have {len(todays_assignments)} task(s) scheduled for today.",
            db,
            plan_id=plan.plan_id,
        )
    if pending_assignments and not has_today_notification("pending_tasks"):
        await _create_patient_notification(
            patient.patient_id,
            "pending_tasks",
            f"{len(pending_assignments)} task(s) are still pending for today.",
            db,
            plan_id=plan.plan_id,
        )
    await db.commit()


@router.get("/profile", response_model=PatientProfileOut)
async def get_profile(
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    assigned_defects = []
    if patient.pre_assigned_defect_ids:
        defect_ids = patient.pre_assigned_defect_ids.get("defect_ids", [])
        if defect_ids:
            defect_result = await db.execute(
                select(Defect).where(Defect.defect_id.in_(defect_ids))
            )
            assigned_defects = [
                {"defect_id": d.defect_id, "name": d.name, "category": d.category}
                for d in defect_result.scalars().all()
            ]

    therapist_name = None
    if patient.assigned_therapist_id:
        therapist = await db.get(Therapist, patient.assigned_therapist_id)
        if therapist:
            therapist_name = therapist.full_name

    return {
        "patient_id": str(patient.patient_id),
        "full_name": patient.full_name,
        "email": patient.email,
        "date_of_birth": patient.date_of_birth,
        "gender": patient.gender,
        "status": patient.status.value,
        "current_streak": patient.current_streak,
        "best_streak": patient.longest_streak,
        "assigned_defects": assigned_defects,
        "therapist_name": therapist_name,
        "primary_diagnosis": patient.primary_diagnosis,
        "member_since": patient.created_at.isoformat() if patient.created_at else None,
    }


@router.get("/home")
async def patient_home(
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    baseline_result = await db.execute(
        select(PatientBaselineResult.result_id)
        .where(PatientBaselineResult.patient_id == patient.patient_id)
        .limit(1)
    )
    has_baseline = baseline_result.scalar_one_or_none() is not None
    plan = await _get_current_plan(patient.patient_id, db)

    today_tasks = 0
    if plan:
        today_idx = date.today().weekday()
        assignment_result = await db.execute(
            select(PlanTaskAssignment).where(
                PlanTaskAssignment.plan_id == plan.plan_id,
                PlanTaskAssignment.day_index == today_idx,
            )
        )
        today_tasks = len(assignment_result.scalars().all())

    return {
        "has_baseline": has_baseline,
        "full_name": patient.full_name,
        "today_tasks": today_tasks,
        "has_approved_plan": plan is not None,
        "plan_status": plan.status if plan else None,
        "plan_name": plan.plan_name if plan else None,
        "plan_start_date": plan.start_date if plan else None,
        "plan_end_date": plan.end_date if plan else None,
    }


@router.get("/tasks", response_model=list[TaskAssignmentOut])
async def get_today_tasks(
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    plan = await _get_current_plan(patient.patient_id, db)
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
    for assignment in assignments:
        task = await db.get(Task, assignment.task_id)
        progress_result = await db.execute(
            select(PatientTaskProgress).where(
                PatientTaskProgress.patient_id == patient.patient_id,
                PatientTaskProgress.task_id == assignment.task_id,
            )
        )
        progress = progress_result.scalar_one_or_none()
        current_level = None
        if progress and progress.current_level_id:
            level = await db.get(TaskLevel, progress.current_level_id)
            current_level = level.level_name if level else None
        out.append(
            TaskAssignmentOut(
                assignment_id=str(assignment.assignment_id),
                task_id=assignment.task_id,
                task_name=task.name if task else assignment.task_id,
                task_mode=task.task_mode if task else "",
                day_index=assignment.day_index,
                status=assignment.status,
                priority_order=assignment.priority_order,
                current_level=current_level,
            )
        )
    return out


@router.get("/tasks/{assignment_id}/prompts", response_model=list[PromptOut])
async def get_prompts(
    assignment_id: str,
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    assignment, _plan, task = await _get_assignment(assignment_id, patient, db)
    target_level_name = await _resolve_task_level_name(patient, task.task_id, db)
    _level, prompts = await _load_level_prompts(task.task_id, target_level_name, db)
    return [_prompt_to_out(prompt) for prompt in prompts]


@router.get("/tasks/{assignment_id}/session-state", response_model=TaskExerciseStateOut)
async def get_task_session_state(
    assignment_id: str,
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    assignment, plan, task = await _get_assignment(assignment_id, patient, db)
    return await _build_task_state(patient, assignment, plan, task, db)


@router.post("/tasks/{assignment_id}/complete")
async def complete_task(
    assignment_id: str,
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    assignment, plan, task = await _get_assignment(assignment_id, patient, db)
    state = await _build_task_state(patient, assignment, plan, task, db)
    session = await _find_active_assignment_session(
        patient.patient_id,
        plan.plan_id,
        str(assignment.assignment_id),
        db,
    )

    if not state.task_complete:
        assignment.status = "pending"
        if session:
            notes = _parse_session_notes(session.session_notes)
            notes["completed"] = True
            notes["completion_status"] = "pending"
            session.session_notes = _serialize_session_notes(notes)
        await db.commit()
        return {
            "message": "Task remains pending until all current exercises are passed.",
            "status": "pending",
        }

    assignment.status = "completed"
    if session:
        notes = _parse_session_notes(session.session_notes)
        notes["completed"] = True
        notes["completion_status"] = "completed"
        session.session_notes = _serialize_session_notes(notes)
    await db.commit()
    return {"message": "Task marked complete", "status": "completed"}


@router.get("/notifications", response_model=list[PatientNotificationOut])
async def list_notifications(
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
    unread_only: bool = False,
):
    await _ensure_patient_notifications(patient, db)
    stmt = select(PatientNotification).where(
        PatientNotification.patient_id == patient.patient_id
    )
    if unread_only:
        stmt = stmt.where(PatientNotification.is_read == False)  # noqa: E712
    stmt = stmt.order_by(PatientNotification.created_at.desc())
    result = await db.execute(stmt)
    notifications = result.scalars().all()
    return [
        PatientNotificationOut(
            id=str(notification.notification_id),
            notification_type=notification.type,
            message=notification.message,
            is_read=notification.is_read,
            created_at=notification.created_at.isoformat(),
            plan_id=str(notification.plan_id) if notification.plan_id else None,
            assignment_id=str(notification.assignment_id) if notification.assignment_id else None,
        )
        for notification in notifications
    ]


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PatientNotification).where(
            PatientNotification.patient_id == patient.patient_id,
            PatientNotification.is_read == False,  # noqa: E712
        )
    )
    notifications = result.scalars().all()
    for notification in notifications:
        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": f"Marked {len(notifications)} notification(s) as read"}


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PatientNotification).where(
            PatientNotification.notification_id == notification_id,
            PatientNotification.patient_id == patient.patient_id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(404, "Notification not found")
    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "Notification marked as read"}
