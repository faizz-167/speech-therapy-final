import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import String, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_patient
from app.database import get_db
from app.models.baseline import PatientBaselineResult
from app.models.content import Defect, Prompt, Task, TaskLevel
from app.models.operations import PatientNotification
from app.models.plan import PlanTaskAssignment, TherapyPlan
from app.models.scoring import AttemptScoreDetail, PatientTaskProgress, Session, SessionPromptAttempt
from app.models.users import Patient, Therapist
from app.schemas.patient import (
    PatientNotificationOut,
    PatientProfileOut,
    PromptOut,
    TaskAssignmentOut,
    TaskExerciseStateOut,
    TodayTasksResponse,
)
from app.utils.plan_lock import patient_has_pending_plan_review
from app.utils.session_notes import default_session_notes, parse_session_notes, serialize_session_notes

LEVEL_ADVANCE = {"beginner": "intermediate", "intermediate": "advanced", "advanced": "advanced"}
LEVEL_DROP = {"advanced": "intermediate", "intermediate": "beginner", "beginner": "beginner"}
LEVEL_ORDER = {"beginner": 0, "intermediate": 1, "advanced": 2}


def _same_iso_week(dt: datetime, today: date) -> bool:
    return dt.isocalendar()[:2] == today.isocalendar()[:2]

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
    initial_level_name: str | None = None,
) -> str:
    progress_result = await db.execute(
        select(PatientTaskProgress).where(
            PatientTaskProgress.patient_id == patient.patient_id,
            PatientTaskProgress.task_id == task_id,
        )
    )
    progress = progress_result.scalar_one_or_none()

    if not (progress and progress.current_level_id):
        # No progress row — fall back to baseline
        baseline_result = await db.execute(
            select(PatientBaselineResult)
            .where(PatientBaselineResult.patient_id == patient.patient_id)
            .order_by(PatientBaselineResult.assessed_on.desc())
        )
        baseline = baseline_result.scalars().first()
        if baseline and baseline.severity_rating:
            return _normalize_task_level_name(baseline.severity_rating)
        return "beginner"

    level = await db.get(TaskLevel, progress.current_level_id)
    current_level_name = level.level_name if level else "beginner"

    # Mid-week: last attempt was in the current ISO week — no recalculation
    today = date.today()
    if progress.last_attempted_at and _same_iso_week(progress.last_attempted_at, today):
        return current_level_name

    # Prior week (or never attempted): run week-over-week recalculation
    # a. Find most recent therapy session for this (patient, task)
    session_row = await db.execute(
        select(Session.session_id)
        .join(SessionPromptAttempt, SessionPromptAttempt.session_id == Session.session_id)
        .join(Prompt, Prompt.prompt_id == SessionPromptAttempt.prompt_id)
        .join(TaskLevel, TaskLevel.level_id == Prompt.level_id)
        .where(
            Session.patient_id == patient.patient_id,
            TaskLevel.task_id == task_id,
            Session.session_type == "therapy",
        )
        .order_by(Session.session_date.desc())
        .limit(1)
    )
    prior_session_id = session_row.scalar_one_or_none()

    if prior_session_id is None:
        return current_level_name

    # b. Get terminal final_score per prompt (highest attempt_number per prompt)
    terminal_scores_result = await db.execute(
        text(
            "SELECT spa.prompt_id, asd.final_score"
            " FROM session_prompt_attempt spa"
            " JOIN attempt_score_detail asd ON asd.attempt_id = spa.attempt_id"
            " WHERE spa.session_id = :session_id"
            "   AND spa.attempt_number = ("
            "       SELECT MAX(spa2.attempt_number)"
            "       FROM session_prompt_attempt spa2"
            "       WHERE spa2.session_id = :session_id"
            "         AND spa2.prompt_id = spa.prompt_id"
            "   )"
        ),
        {"session_id": str(prior_session_id)},
    )
    rows = terminal_scores_result.fetchall()
    final_scores = [float(r[1]) for r in rows if r[1] is not None]

    if not final_scores:
        return current_level_name

    # c. Average score
    average_score = sum(final_scores) / len(final_scores)

    # d. Threshold decision
    if average_score >= 75:
        resolved_level = LEVEL_ADVANCE.get(current_level_name, current_level_name)
    elif average_score >= 60:
        resolved_level = current_level_name
    else:
        resolved_level = LEVEL_DROP.get(current_level_name, current_level_name)

    # e. Floor clamp against initial_level_name
    if initial_level_name:
        initial_order = LEVEL_ORDER.get(initial_level_name.lower(), 0)
        resolved_order = LEVEL_ORDER.get(resolved_level.lower(), 0)
        if resolved_order < initial_order:
            resolved_level = initial_level_name.lower()

    # f. Update patient_task_progress.current_level_id
    new_level_result = await db.execute(
        select(TaskLevel).where(
            TaskLevel.task_id == task_id,
            cast(TaskLevel.level_name, String) == resolved_level,
        )
    )
    new_level = new_level_result.scalar_one_or_none()
    if new_level and progress:
        progress.current_level_id = new_level.level_id
        await db.commit()

    return resolved_level


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


def _queue_item_to_prompt_out(item: dict, prompt: Prompt) -> PromptOut:
    return PromptOut(
        prompt_id=prompt.prompt_id,
        prompt_type=prompt.prompt_type,
        task_mode=prompt.task_mode,
        instruction=prompt.instruction,
        display_content=prompt.display_content,
        target_response=prompt.target_response,
        scenario_context=prompt.scenario_context,
    )


async def _ensure_session_queue(
    patient: Patient,
    assignment: PlanTaskAssignment,
    task: Task,
    session: Session,
    notes: dict,
    db: AsyncSession,
) -> dict:
    if notes.get("queue_initialized") and notes.get("queue_items"):
        return notes

    target_level_name = await _resolve_task_level_name(
        patient, task.task_id, db,
        initial_level_name=assignment.initial_level_name,
    )
    _level, prompts = await _load_level_prompts(task.task_id, target_level_name, db)

    notes["queue_items"] = [
        {
            "queue_item_id": str(uuid.uuid4()),
            "prompt_id": prompt.prompt_id,
            "level_name": target_level_name,
            "source_type": "planned",
            "status": "pending",
            "attempts_used": 0,
            "adapted_from_level": None,
            "reason_code": None,
        }
        for prompt in prompts
    ]
    notes["queue_initialized"] = True
    notes["current_queue_level"] = target_level_name
    session.session_notes = serialize_session_notes(notes)
    await db.commit()
    await db.refresh(session)
    return parse_session_notes(session.session_notes)


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
        notes = parse_session_notes(session.session_notes)
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
        session_notes=serialize_session_notes(
            default_session_notes(
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
    if await patient_has_pending_plan_review(patient.patient_id, db):
        return TaskExerciseStateOut(
            session_id="",
            current_level="",
            total_prompts=0,
            completed_prompts=0,
            task_complete=False,
            current_prompt=None,
            escalated=True,
            escalation_message="Your therapist must approve a regenerated plan before you can continue.",
        )

    session = await _get_or_create_assignment_session(patient, plan, assignment, db)
    notes = parse_session_notes(session.session_notes)
    notes = await _ensure_session_queue(patient, assignment, task, session, notes, db)

    if notes.get("escalated"):
        return TaskExerciseStateOut(
            session_id=str(session.session_id),
            current_level="",
            total_prompts=0,
            completed_prompts=0,
            task_complete=False,
            current_prompt=None,
            escalated=True,
            escalation_message="Your therapist is reviewing this task. Please check back later.",
        )
    queue_items = notes.get("queue_items") or []
    terminal_statuses = {"passed", "failed_terminal", "skipped_due_to_lock"}
    completed_count = sum(1 for item in queue_items if item.get("status") in terminal_statuses)
    pending_item = next((item for item in queue_items if item.get("status") == "pending"), None)
    current_level_name = str(
        (pending_item or {}).get("level_name")
        or notes.get("current_queue_level")
        or assignment.initial_level_name
        or "beginner"
    )

    current_prompt = None
    if pending_item:
        prompt = await db.get(Prompt, pending_item.get("prompt_id"))
        if prompt:
            current_prompt = _queue_item_to_prompt_out(pending_item, prompt)

    return TaskExerciseStateOut(
        session_id=str(session.session_id),
        current_level=current_level_name,
        total_prompts=len(queue_items),
        completed_prompts=completed_count,
        task_complete=bool(queue_items) and pending_item is None,
        current_prompt=current_prompt,
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


async def _recalculate_streak(patient: Patient, db: AsyncSession) -> tuple[int, int]:
    """Recalculate current and best streak from historical attempt data.

    Returns (current_streak, longest_streak). Persists updated values to DB.
    """
    rows_result = await db.execute(
        text(
            "SELECT DISTINCT DATE(asd.created_at AT TIME ZONE 'UTC')"
            " FROM attempt_score_detail asd"
            " JOIN session_prompt_attempt spa ON spa.attempt_id = asd.attempt_id"
            " JOIN session s ON s.session_id = spa.session_id"
            " WHERE s.patient_id = :pid"
            " ORDER BY 1 DESC"
        ),
        {"pid": str(patient.patient_id)},
    )
    activity_dates = sorted({r[0] for r in rows_result.fetchall()}, reverse=True)

    if not activity_dates:
        return 0, int(patient.longest_streak or 0)

    today_utc = datetime.now(timezone.utc).date()

    # Streak is broken if most recent activity is more than 1 day ago
    if activity_dates[0] < today_utc - timedelta(days=1):
        current_streak = 0
    else:
        current_streak = 1
        for i in range(1, len(activity_dates)):
            delta = (activity_dates[i - 1] - activity_dates[i]).days
            if delta == 1:
                current_streak += 1
            elif delta == 0:
                continue
            else:
                break

    # Best streak: scan all dates for longest consecutive run
    best_streak = current_streak
    run = 1
    for i in range(1, len(activity_dates)):
        delta = (activity_dates[i - 1] - activity_dates[i]).days
        if delta == 1:
            run += 1
            best_streak = max(best_streak, run)
        elif delta == 0:
            continue
        else:
            run = 1

    best_streak = max(best_streak, int(patient.longest_streak or 0))

    # Persist only when values changed to avoid unnecessary writes
    if patient.current_streak != current_streak or patient.longest_streak != best_streak:
        await db.execute(
            text(
                "UPDATE patient SET current_streak=:cs, longest_streak=:ls"
                " WHERE patient_id=:pid"
            ),
            {"cs": current_streak, "ls": best_streak, "pid": str(patient.patient_id)},
        )
        await db.commit()

    return current_streak, best_streak


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

    # Recalculate streak on every profile fetch — keeps it accurate for both
    # new users (updated in real-time after attempts) and existing users whose
    # historical data was never counted.
    current_streak, best_streak = await _recalculate_streak(patient, db)

    return {
        "patient_id": str(patient.patient_id),
        "full_name": patient.full_name,
        "email": patient.email,
        "date_of_birth": patient.date_of_birth,
        "gender": patient.gender,
        "status": patient.status.value,
        "current_streak": current_streak,
        "best_streak": best_streak,
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


@router.get("/tasks", response_model=TodayTasksResponse)
async def get_today_tasks(
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    if await patient_has_pending_plan_review(patient.patient_id, db):
        return TodayTasksResponse(assignments=[], any_escalated=True)

    plan = await _get_current_plan(patient.patient_id, db)
    if not plan:
        return TodayTasksResponse(assignments=[], any_escalated=False)

    today_idx = date.today().weekday()
    assignment_result = await db.execute(
        select(PlanTaskAssignment).where(
            PlanTaskAssignment.plan_id == plan.plan_id,
            PlanTaskAssignment.day_index == today_idx,
        )
    )
    today_assignments = assignment_result.scalars().all()
    out = []
    for assignment in today_assignments:
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
        if current_level is None:
            current_level = assignment.initial_level_name
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

    return TodayTasksResponse(assignments=out, any_escalated=False)


@router.get("/tasks/{assignment_id}/prompts", response_model=list[PromptOut])
async def get_prompts(
    assignment_id: str,
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    assignment, _plan, task = await _get_assignment(assignment_id, patient, db)
    target_level_name = await _resolve_task_level_name(
        patient, task.task_id, db,
        initial_level_name=assignment.initial_level_name,
    )
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
            notes = parse_session_notes(session.session_notes)
            notes["completed"] = True
            notes["completion_status"] = "pending"
            session.session_notes = serialize_session_notes(notes)
        await db.commit()
        return {
            "message": "Task remains pending until all current exercises are passed.",
            "status": "pending",
        }

    assignment.status = "completed"
    if session:
        notes = parse_session_notes(session.session_notes)
        notes["completed"] = True
        notes["completion_status"] = "completed"
        session.session_notes = serialize_session_notes(notes)
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
