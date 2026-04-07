import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.models.users import Therapist, Patient, PatientStatus

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)
COOKIE_NAME = "speechpath_token"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def generate_therapist_code(length: int = 8) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def create_access_token(data: dict) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    return jwt.encode({**data, "exp": expire}, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(key=COOKIE_NAME, httponly=True, samesite="lax", path="/")


def get_request_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if credentials and credentials.credentials:
        return credentials.credentials

    cookie_token = request.cookies.get(COOKIE_NAME)
    if cookie_token:
        return cookie_token

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


async def require_therapist(
    token: Annotated[str, Depends(get_request_token)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Therapist:
    payload = decode_token(token)
    if payload.get("role") != "therapist":
        raise HTTPException(status_code=403, detail="Therapist access required")
    result = await db.execute(select(Therapist).where(Therapist.therapist_id == uuid.UUID(payload["sub"])))
    therapist = result.scalar_one_or_none()
    if not therapist:
        raise HTTPException(status_code=404, detail="Therapist not found")
    return therapist


async def require_patient(
    token: Annotated[str, Depends(get_request_token)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Patient:
    payload = decode_token(token)
    if payload.get("role") != "patient":
        raise HTTPException(status_code=403, detail="Patient access required")
    result = await db.execute(select(Patient).where(Patient.patient_id == uuid.UUID(payload["sub"])))
    patient = result.scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if patient.status != PatientStatus.approved:
        raise HTTPException(status_code=403, detail="Account pending therapist approval")
    return patient
