import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, ForeignKey, Numeric, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class BaselineAssessment(Base):
    __tablename__ = "baseline_assessment"
    baseline_id: Mapped[str] = mapped_column(String, primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    domain: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    sections: Mapped[list["BaselineSection"]] = relationship(
        "BaselineSection", back_populates="assessment", order_by="BaselineSection.order_index"
    )


class BaselineDefectMapping(Base):
    __tablename__ = "baseline_defect_mapping"
    mapping_id: Mapped[str] = mapped_column(String, primary_key=True)
    baseline_id: Mapped[str] = mapped_column(String, ForeignKey("baseline_assessment.baseline_id"))
    defect_id: Mapped[str] = mapped_column(String, ForeignKey("defect.defect_id"))


class BaselineSection(Base):
    __tablename__ = "baseline_section"
    section_id: Mapped[str] = mapped_column(String, primary_key=True)
    baseline_id: Mapped[str] = mapped_column(String, ForeignKey("baseline_assessment.baseline_id"))
    section_name: Mapped[str] = mapped_column(String)
    instructions: Mapped[str | None] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer)
    assessment: Mapped["BaselineAssessment"] = relationship("BaselineAssessment", back_populates="sections")
    items: Mapped[list["BaselineItem"]] = relationship(
        "BaselineItem", back_populates="section", order_by="BaselineItem.order_index"
    )


class BaselineItem(Base):
    __tablename__ = "baseline_item"
    item_id: Mapped[str] = mapped_column(String, primary_key=True)
    section_id: Mapped[str] = mapped_column(String, ForeignKey("baseline_section.section_id"))
    order_index: Mapped[int] = mapped_column(Integer)
    task_name: Mapped[str | None] = mapped_column(String)
    instruction: Mapped[str | None] = mapped_column(Text)
    display_content: Mapped[str | None] = mapped_column(Text)
    expected_output: Mapped[str | None] = mapped_column(Text)
    response_type: Mapped[str | None] = mapped_column(String)
    target_phoneme: Mapped[str | None] = mapped_column(String)
    formula_mode: Mapped[str | None] = mapped_column(String)
    formula_weights: Mapped[dict | None] = mapped_column(JSONB)
    fusion_weights: Mapped[dict | None] = mapped_column(JSONB)
    wpm_range: Mapped[dict | None] = mapped_column(JSONB)
    defect_codes: Mapped[dict | None] = mapped_column(JSONB)
    max_score: Mapped[int | None] = mapped_column(Integer)
    section: Mapped["BaselineSection"] = relationship("BaselineSection", back_populates="items")


class PatientBaselineResult(Base):
    __tablename__ = "patient_baseline_result"
    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient.patient_id"))
    baseline_id: Mapped[str] = mapped_column(String, ForeignKey("baseline_assessment.baseline_id"))
    therapist_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("therapist.therapist_id"))
    assessed_on: Mapped[str] = mapped_column(String)
    raw_score: Mapped[int | None] = mapped_column(Integer)
    severity_rating: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(Text)


class BaselineItemResult(Base):
    __tablename__ = "baseline_item_result"
    item_result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_baseline_result.result_id"))
    item_id: Mapped[str] = mapped_column(String, ForeignKey("baseline_item.item_id"))
    score_given: Mapped[int | None] = mapped_column(Integer)
    error_noted: Mapped[str | None] = mapped_column(Text)
