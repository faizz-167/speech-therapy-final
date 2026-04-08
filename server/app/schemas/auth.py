from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import date


class TherapistRegister(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    years_of_experience: int | None = None
    license_number: str | None = None
    specialization: str | None = None


class PatientRegister(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    date_of_birth: date
    gender: str | None = None
    therapist_code: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: str
    full_name: str


class MeResponse(BaseModel):
    user_id: str
    email: str
    full_name: str
    role: str
