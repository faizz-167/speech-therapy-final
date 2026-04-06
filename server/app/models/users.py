import uuid
from datetime import datetime, timezone, date
from sqlalchemy import String, Integer, Text, Enum as SAEnum, ForeignKey, TIMESTAMP, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


class PatientStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"


class Therapist(Base):
    __tablename__ = "therapist"

    therapist_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    therapist_code: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    license_number: Mapped[str | None] = mapped_column(String, nullable=True)
    specialization: Mapped[str | None] = mapped_column(String, nullable=True)
    years_of_experience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    role: Mapped[str] = mapped_column(String, default="therapist")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))

    patients: Mapped[list["Patient"]] = relationship("Patient", back_populates="therapist")


class Patient(Base):
    __tablename__ = "patient"

    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    gender: Mapped[str | None] = mapped_column(String, nullable=True)
    primary_diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    clinical_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    pre_assigned_defect_ids: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    assigned_therapist_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("therapist.therapist_id"), nullable=True)
    status: Mapped[PatientStatus] = mapped_column(SAEnum(PatientStatus, name="patient_status", create_type=False), default=PatientStatus.pending)
    role: Mapped[str] = mapped_column(String, default="patient")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))

    therapist: Mapped["Therapist | None"] = relationship("Therapist", back_populates="patients")
