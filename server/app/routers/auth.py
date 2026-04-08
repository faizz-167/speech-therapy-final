import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.schemas.auth import TherapistRegister, PatientRegister, LoginRequest, TokenResponse, MeResponse
from app.models.users import Therapist, Patient, PatientStatus
from app.models.operations import TherapistNotification
from app.auth import (
    hash_password, verify_password, generate_therapist_code,
    create_access_token, decode_token, get_request_token,
    set_auth_cookie, clear_auth_cookie,
)

router = APIRouter()


@router.post("/register/therapist", response_model=TokenResponse)
async def register_therapist(
    body: TherapistRegister,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(Therapist).where(Therapist.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Email already registered")
    therapist = Therapist(
        therapist_id=uuid.uuid4(),
        therapist_code=generate_therapist_code(),
        full_name=body.full_name,
        email=body.email,
        password_hash=hash_password(body.password),
        years_of_experience=body.years_of_experience,
        license_number=body.license_number,
        specialization=body.specialization,
    )
    db.add(therapist)
    await db.commit()
    await db.refresh(therapist)
    token = create_access_token({"sub": str(therapist.therapist_id), "role": "therapist"})
    set_auth_cookie(response, token)
    return TokenResponse(
        access_token=token,
        role="therapist",
        user_id=str(therapist.therapist_id),
        full_name=therapist.full_name,
    )


@router.post("/register/patient", response_model=TokenResponse)
async def register_patient(
    body: PatientRegister,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Therapist).where(Therapist.therapist_code == body.therapist_code))
    therapist = result.scalar_one_or_none()
    if not therapist:
        raise HTTPException(400, "Invalid therapist code")
    existing = await db.execute(select(Patient).where(Patient.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Email already registered")
    patient = Patient(
        patient_id=uuid.uuid4(),
        email=body.email,
        password_hash=hash_password(body.password),
        full_name=body.full_name,
        date_of_birth=body.date_of_birth,
        gender=body.gender,
        assigned_therapist_id=therapist.therapist_id,
        status=PatientStatus.pending,
    )
    db.add(patient)
    await db.commit()
    notification = TherapistNotification(
        therapist_id=therapist.therapist_id,
        type="patient_registered",
        patient_id=patient.patient_id,
        message=f"New patient {patient.full_name} registered and is awaiting your approval.",
    )
    db.add(notification)
    await db.commit()
    await db.refresh(patient)
    token = create_access_token({"sub": str(patient.patient_id), "role": "patient"})
    set_auth_cookie(response, token)
    return TokenResponse(
        access_token=token,
        role="patient",
        user_id=str(patient.patient_id),
        full_name=patient.full_name,
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Therapist).where(Therapist.email == body.email))
    therapist = result.scalar_one_or_none()
    if therapist and verify_password(body.password, therapist.password_hash):
        token = create_access_token({"sub": str(therapist.therapist_id), "role": "therapist"})
        set_auth_cookie(response, token)
        return TokenResponse(
            access_token=token,
            role="therapist",
            user_id=str(therapist.therapist_id),
            full_name=therapist.full_name,
        )
    result = await db.execute(select(Patient).where(Patient.email == body.email))
    patient = result.scalar_one_or_none()
    if patient and verify_password(body.password, patient.password_hash):
        if patient.status == PatientStatus.pending:
            raise HTTPException(403, "Account pending therapist approval")
        token = create_access_token({"sub": str(patient.patient_id), "role": "patient"})
        set_auth_cookie(response, token)
        return TokenResponse(
            access_token=token,
            role="patient",
            user_id=str(patient.patient_id),
            full_name=patient.full_name,
        )
    raise HTTPException(401, "Invalid credentials")


@router.get("/me", response_model=MeResponse)
async def me(
    token: Annotated[str, Depends(get_request_token)],
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    payload = decode_token(token)
    role = payload.get("role")
    if role == "therapist":
        result = await db.execute(
            select(Therapist).where(Therapist.therapist_id == uuid.UUID(payload["sub"]))
        )
        therapist = result.scalar_one_or_none()
        if not therapist:
            raise HTTPException(404, "Therapist not found")
        return MeResponse(
            user_id=str(therapist.therapist_id),
            email=therapist.email,
            full_name=therapist.full_name,
            role="therapist",
        )
    if role == "patient":
        result = await db.execute(
            select(Patient).where(Patient.patient_id == uuid.UUID(payload["sub"]))
        )
        patient = result.scalar_one_or_none()
        if not patient:
            raise HTTPException(404, "Patient not found")
        if patient.status != PatientStatus.approved:
            clear_auth_cookie(response)
            raise HTTPException(403, "Account pending therapist approval")
        return MeResponse(
            user_id=str(patient.patient_id),
            email=patient.email,
            full_name=patient.full_name,
            role="patient",
        )
    raise HTTPException(401, "Invalid token")


@router.post("/logout")
async def logout(response: Response):
    clear_auth_cookie(response)
    return {"message": "Logged out"}
