import uuid
from datetime import datetime, timezone, date
from sqlalchemy import String, Integer, Text, Boolean, ForeignKey, TIMESTAMP, Date, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class TherapyPlan(Base):
    __tablename__ = "therapy_plan"

    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient.patient_id"))
    therapist_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("therapist.therapist_id"))
    plan_name: Mapped[str] = mapped_column(String)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, default="draft")
    goals: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))

    assignments: Mapped[list["PlanTaskAssignment"]] = relationship(
        "PlanTaskAssignment", back_populates="plan", cascade="all, delete-orphan"
    )
    revision_history: Mapped[list["PlanRevisionHistory"]] = relationship("PlanRevisionHistory", back_populates="plan")


class PlanTaskAssignment(Base):
    __tablename__ = "plan_task_assignment"
    __table_args__ = (UniqueConstraint("plan_id", "day_index", "priority_order"),)

    assignment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("therapy_plan.plan_id"))
    task_id: Mapped[str] = mapped_column(String, ForeignKey("task.task_id"))
    therapist_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("therapist.therapist_id"))
    day_index: Mapped[int | None] = mapped_column(Integer)
    priority_order: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String, default="pending")
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    clinical_rationale: Mapped[str | None] = mapped_column(Text)

    plan: Mapped["TherapyPlan"] = relationship("TherapyPlan", back_populates="assignments")


class PlanRevisionHistory(Base):
    __tablename__ = "plan_revision_history"

    revision_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("therapy_plan.plan_id"))
    therapist_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("therapist.therapist_id"))
    action: Mapped[str] = mapped_column(String)
    assignment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("plan_task_assignment.assignment_id"), nullable=True)
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))

    plan: Mapped["TherapyPlan"] = relationship("TherapyPlan", back_populates="revision_history")
