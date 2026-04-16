from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from typing import Annotated

from app.database import get_db
from app.auth import require_therapist
from app.models.users import Therapist, Patient, PatientStatus
from app.models.content import Defect, Task
from app.models.operations import PatientNotification, TherapistNotification
from app.models.baseline import PatientBaselineResult
from app.models.plan import TherapyPlan, PlanRevisionHistory
from app.models.scoring import Session
from app.utils.session_notes import parse_session_notes
from app.schemas.therapist import (
    DashboardResponse, PatientListItem, ApprovePatientRequest,
    TherapistProfileResponse, DefectItem, NotificationOut,
    AdaptationActivityOut, AdaptationEventOut, AdaptationStepOut,
    RegeneratedPlanOut, RegeneratedAssignmentOut,
)

router = APIRouter()


@router.get("/profile", response_model=TherapistProfileResponse)
async def get_profile(therapist: Annotated[Therapist, Depends(require_therapist)]):
    return TherapistProfileResponse(
        therapist_id=str(therapist.therapist_id),
        full_name=therapist.full_name,
        email=therapist.email,
        therapist_code=therapist.therapist_code,
        license_number=therapist.license_number,
        specialization=therapist.specialization,
        years_of_experience=therapist.years_of_experience,
    )


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    total_result = await db.execute(
        select(func.count(Patient.patient_id)).where(
            Patient.assigned_therapist_id == therapist.therapist_id,
        )
    )
    total = total_result.scalar() or 0

    approved_result = await db.execute(
        select(func.count(Patient.patient_id)).where(
            Patient.assigned_therapist_id == therapist.therapist_id,
            Patient.status == PatientStatus.approved,
        )
    )
    approved = approved_result.scalar() or 0

    pending_result = await db.execute(
        select(func.count(Patient.patient_id)).where(
            Patient.assigned_therapist_id == therapist.therapist_id,
            Patient.status == PatientStatus.pending,
        )
    )
    pending = pending_result.scalar() or 0

    no_baseline_subq = (
        select(PatientBaselineResult.result_id)
        .where(PatientBaselineResult.patient_id == Patient.patient_id)
        .correlate(Patient)
        .exists()
    )
    no_baseline_result = await db.execute(
        select(func.count(Patient.patient_id)).where(
            Patient.assigned_therapist_id == therapist.therapist_id,
            Patient.status == PatientStatus.approved,
            ~no_baseline_subq,
        )
    )
    patients_without_baseline = no_baseline_result.scalar() or 0

    no_plan_subq = (
        select(TherapyPlan.plan_id)
        .where(
            TherapyPlan.patient_id == Patient.patient_id,
            TherapyPlan.status == "approved",
        )
        .correlate(Patient)
        .exists()
    )
    no_plan_result = await db.execute(
        select(func.count(Patient.patient_id)).where(
            Patient.assigned_therapist_id == therapist.therapist_id,
            Patient.status == PatientStatus.approved,
            ~no_plan_subq,
        )
    )
    patients_without_approved_plan = no_plan_result.scalar() or 0

    plans_result = await db.execute(
        select(func.count(TherapyPlan.plan_id)).where(
            TherapyPlan.therapist_id == therapist.therapist_id,
            TherapyPlan.status == "draft",
        )
    )
    plans_pending_approval = plans_result.scalar() or 0

    notif_result = await db.execute(
        select(func.count(TherapistNotification.notification_id)).where(
            TherapistNotification.therapist_id == therapist.therapist_id,
            TherapistNotification.is_read == False,  # noqa: E712
        )
    )
    unread_notification_count = notif_result.scalar() or 0

    return DashboardResponse(
        total_patients=total,
        approved_patients=approved,
        pending_patients=pending,
        patients_without_baseline=patients_without_baseline,
        patients_without_approved_plan=patients_without_approved_plan,
        plans_pending_approval=plans_pending_approval,
        unread_notification_count=unread_notification_count,
    )


@router.get("/patients", response_model=list[PatientListItem])
async def list_patients(
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Patient).where(Patient.assigned_therapist_id == therapist.therapist_id)
    )
    patients = result.scalars().all()
    return [
        PatientListItem(
            patient_id=str(p.patient_id),
            full_name=p.full_name,
            email=p.email,
            status=p.status.value,
            date_of_birth=p.date_of_birth,
            gender=p.gender,
            pre_assigned_defect_ids=p.pre_assigned_defect_ids,
            created_at=str(p.created_at),
        )
        for p in patients
    ]


@router.get("/patients/{patient_id}", response_model=PatientListItem)
async def get_patient(
    patient_id: str,
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Patient).where(
            Patient.patient_id == patient_id,
            Patient.assigned_therapist_id == therapist.therapist_id,
        )
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(404, "Patient not found")
    return PatientListItem(
        patient_id=str(patient.patient_id),
        full_name=patient.full_name,
        email=patient.email,
        status=patient.status.value,
        date_of_birth=patient.date_of_birth,
        gender=patient.gender,
        pre_assigned_defect_ids=patient.pre_assigned_defect_ids,
        created_at=str(patient.created_at),
    )


@router.post("/patients/{patient_id}/approve")
async def approve_patient(
    patient_id: str,
    body: ApprovePatientRequest,
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Patient).where(
            Patient.patient_id == patient_id,
            Patient.assigned_therapist_id == therapist.therapist_id,
        )
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(404, "Patient not found")
    defect_result = await db.execute(
        select(Defect.defect_id).where(Defect.defect_id.in_(body.defect_ids))
    )
    valid_defect_ids = {row[0] for row in defect_result.all()}
    if len(valid_defect_ids) != len(set(body.defect_ids)):
        raise HTTPException(400, "One or more selected defects are invalid")
    patient.status = PatientStatus.approved
    patient.pre_assigned_defect_ids = {"defect_ids": body.defect_ids}
    patient.primary_diagnosis = body.primary_diagnosis
    patient.clinical_notes = body.clinical_notes
    db.add(PatientNotification(
        patient_id=patient.patient_id,
        type="therapist_approved",
        message="Your therapist approved your account. You can begin your baseline assessment.",
    ))
    await db.commit()
    return {"message": "Patient approved"}


@router.post("/patients/{patient_id}/reject")
async def reject_patient(
    patient_id: str,
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Patient).where(
            Patient.patient_id == patient_id,
            Patient.assigned_therapist_id == therapist.therapist_id,
        )
    )
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(404, "Patient not found")
    await db.delete(patient)
    await db.commit()
    return {"message": "Patient rejected"}


@router.get("/notifications", response_model=list[NotificationOut])
async def list_notifications(
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
    unread_only: bool = False,
):
    stmt = select(TherapistNotification).where(
        TherapistNotification.therapist_id == therapist.therapist_id
    )
    if unread_only:
        stmt = stmt.where(TherapistNotification.is_read == False)  # noqa: E712
    stmt = stmt.order_by(TherapistNotification.created_at.desc())
    result = await db.execute(stmt)
    notifications = result.scalars().all()
    return [
        NotificationOut(
            id=str(n.notification_id),
            notification_type=n.type,
            message=n.message,
            is_read=n.is_read,
            created_at=n.created_at.isoformat(),
            patient_id=str(n.patient_id) if n.patient_id else None,
            attempt_id=str(n.attempt_id) if n.attempt_id else None,
        )
        for n in notifications
    ]


@router.post("/notifications/read-all")
async def mark_all_notifications_read(
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TherapistNotification).where(
            TherapistNotification.therapist_id == therapist.therapist_id,
            TherapistNotification.is_read == False,  # noqa: E712
        )
    )
    notifications = result.scalars().all()
    now = datetime.now(timezone.utc)
    for n in notifications:
        n.is_read = True
        n.read_at = now
    await db.commit()
    return {"message": f"Marked {len(notifications)} notification(s) as read"}


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(TherapistNotification).where(
            TherapistNotification.notification_id == notification_id,
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(404, "Notification not found")
    if notification.therapist_id != therapist.therapist_id:
        raise HTTPException(403, "Access denied")
    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc)
    await db.commit()
    return {"message": "Notification marked as read"}


@router.get("/defects", response_model=list[DefectItem])
async def list_defects(
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Defect))
    defects = result.scalars().all()
    return [
        DefectItem(defect_id=d.defect_id, code=d.code, name=d.name, category=d.category)
        for d in defects
    ]


@router.get("/patients/{patient_id}/adaptation-activity", response_model=AdaptationActivityOut)
async def get_adaptation_activity(
    patient_id: str,
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    # Verify patient belongs to this therapist
    patient_result = await db.execute(
        select(Patient).where(
            Patient.patient_id == patient_id,
            Patient.assigned_therapist_id == therapist.therapist_id,
        )
    )
    if not patient_result.scalar_one_or_none():
        raise HTTPException(404, "Patient not found")

    # Fetch all sessions for the patient
    sessions_result = await db.execute(
        select(Session)
        .where(Session.patient_id == patient_id)
        .order_by(Session.session_date.desc())
    )
    sessions = sessions_result.scalars().all()

    # Filter to sessions that have at least one adaptation.
    # Use parse_session_notes so all keys are guaranteed present with defaults,
    # even for sessions recorded before the escalation fields were introduced.
    adaptation_data: list[tuple[Session, dict]] = []
    session_task_ids: set[str] = set()
    for session in sessions:
        notes = parse_session_notes(session.session_notes)
        if int(notes.get("adaptive_interventions") or 0) < 1:
            continue
        task_id = notes.get("task_id")
        if task_id:
            session_task_ids.add(str(task_id))
        adaptation_data.append((session, notes))

    # Fetch auto-regenerated plans for this patient (identified via revision history)
    regen_plans_result = await db.execute(
        select(TherapyPlan)
        .join(PlanRevisionHistory, TherapyPlan.plan_id == PlanRevisionHistory.plan_id)
        .where(
            TherapyPlan.patient_id == patient_id,
            PlanRevisionHistory.action == "auto_regenerated_after_escalation",
        )
        .options(
            selectinload(TherapyPlan.assignments),
            selectinload(TherapyPlan.revision_history),
        )
        .order_by(TherapyPlan.created_at.desc())
    )
    regen_plans = regen_plans_result.scalars().unique().all()

    assignment_task_ids: set[str] = set()
    for plan in regen_plans:
        for assignment in plan.assignments:
            assignment_task_ids.add(str(assignment.task_id))

    # Batch-fetch task names for all collected task IDs
    all_task_ids = session_task_ids | assignment_task_ids
    task_names: dict[str, str] = {}
    if all_task_ids:
        tasks_result = await db.execute(
            select(Task.task_id, Task.name).where(Task.task_id.in_(all_task_ids))
        )
        task_names = {row[0]: row[1] for row in tasks_result.all()}

    # Build RegeneratedPlanOut objects sorted chronologically (ASC) for pairing
    def _build_regen_plan_out(plan) -> RegeneratedPlanOut:
        regen_note: str | None = None
        for rev in plan.revision_history:
            if rev.action == "auto_regenerated_after_escalation":
                regen_note = rev.note
                break
        return RegeneratedPlanOut(
            plan_id=str(plan.plan_id),
            plan_name=plan.plan_name,
            status=plan.status,
            created_at=plan.created_at.isoformat(),
            regeneration_note=regen_note,
            assignments=[
                RegeneratedAssignmentOut(
                    assignment_id=str(a.assignment_id),
                    task_id=str(a.task_id),
                    task_name=task_names.get(str(a.task_id), "Unknown Task"),
                    initial_level_name=a.initial_level_name,
                    day_index=a.day_index,
                )
                for a in plan.assignments
            ],
        )

    regen_plans_asc = sorted(regen_plans, key=lambda p: p.created_at)
    regen_plans_out_asc = [_build_regen_plan_out(p) for p in regen_plans_asc]

    # Pair each escalated session (chronological ASC) with the matching regen plan.
    # A session is "escalated" when adaptive_interventions >= 2, regardless of whether
    # the notes["escalated"] boolean was written (some older sessions may be missing it).
    def _is_escalated(n: dict) -> bool:
        return bool(n.get("escalated")) or int(n.get("adaptive_interventions") or 0) >= 2

    escalated_asc = sorted(
        [(s, n) for s, n in adaptation_data if _is_escalated(n)],
        key=lambda x: x[0].session_date,
    )
    linked_plan_map: dict[str, RegeneratedPlanOut] = {}
    for i, (esession, _) in enumerate(escalated_asc):
        if i < len(regen_plans_out_asc):
            linked_plan_map[str(esession.session_id)] = regen_plans_out_asc[i]

    # Build adaptation event list (adaptation_data is already DESC by session_date)
    adaptation_events: list[AdaptationEventOut] = []
    for session, notes in adaptation_data:
        adaptive_count = int(notes.get("adaptive_interventions") or 0)
        is_escalated = _is_escalated(notes)

        # Resolve task_id from multiple possible locations in notes
        adaptation_report = notes.get("adaptation_report")
        task_id = (
            notes.get("task_id")
            or (adaptation_report or {}).get("task_id")
            or ""
        )
        task_name = task_names.get(str(task_id), "Unknown Task")
        if isinstance(adaptation_report, dict) and adaptation_report.get("task_name"):
            task_name = adaptation_report["task_name"]

        adaptation_events.append(
            AdaptationEventOut(
                session_id=str(session.session_id),
                session_date=session.session_date.isoformat(),
                task_id=str(task_id),
                task_name=task_name,
                adaptation_count=adaptive_count,
                escalated=is_escalated,
                adaptation_history=[
                    AdaptationStepOut(
                        from_level=step.get("from_level", ""),
                        to_level=step.get("to_level", ""),
                        attempts_used=int(step.get("attempts_used") or 0),
                        reason=step.get("reason", ""),
                        final_score=float(step.get("final_score") or 0),
                    )
                    for step in (notes.get("adaptation_history") or [])
                ],
                adaptation_report=adaptation_report if isinstance(adaptation_report, dict) else None,
                linked_plan=linked_plan_map.get(str(session.session_id)),
            )
        )

    return AdaptationActivityOut(
        adaptation_events=adaptation_events,
        regenerated_plans=[_build_regen_plan_out(p) for p in regen_plans],
    )
