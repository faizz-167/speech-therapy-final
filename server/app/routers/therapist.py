from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from typing import Annotated

from app.database import get_db
from app.auth import require_therapist
from app.models.users import Therapist, Patient, PatientStatus
from app.models.content import Defect
from app.models.operations import PatientNotification, TherapistNotification
from app.models.baseline import PatientBaselineResult
from app.models.plan import TherapyPlan
from app.schemas.therapist import (
    DashboardResponse, PatientListItem, ApprovePatientRequest,
    TherapistProfileResponse, DefectItem, NotificationOut,
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
