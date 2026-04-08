from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Annotated

from app.database import get_db
from app.auth import require_therapist
from app.models.users import Therapist, Patient, PatientStatus
from app.models.content import Defect
from app.schemas.therapist import (
    DashboardResponse, PatientListItem, ApprovePatientRequest,
    TherapistProfileResponse, DefectItem,
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
    result = await db.execute(
        select(Patient).where(Patient.assigned_therapist_id == therapist.therapist_id)
    )
    patients = result.scalars().all()
    return DashboardResponse(
        total_patients=len(patients),
        approved_patients=sum(1 for p in patients if p.status == PatientStatus.approved),
        pending_patients=sum(1 for p in patients if p.status == PatientStatus.pending),
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
