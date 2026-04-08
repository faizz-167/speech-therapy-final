import uuid
from datetime import datetime, timezone, date
from sqlalchemy import String, Integer, Text, ForeignKey, Numeric, TIMESTAMP, Date, UniqueConstraint
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
    administration_method: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))

    sections: Mapped[list["BaselineSection"]] = relationship(
        "BaselineSection", back_populates="assessment", order_by="BaselineSection.order_index"
    )


class BaselineDefectMapping(Base):
    __tablename__ = "baseline_defect_mapping"
    __table_args__ = (UniqueConstraint("baseline_id", "defect_id"),)

    mapping_id: Mapped[str] = mapped_column(String, primary_key=True)
    baseline_id: Mapped[str] = mapped_column(String, ForeignKey("baseline_assessment.baseline_id"))
    defect_id: Mapped[str] = mapped_column(String, ForeignKey("defect.defect_id"))
    relevance_level: Mapped[str | None] = mapped_column(String, nullable=True)
    clinical_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class BaselineSection(Base):
    __tablename__ = "baseline_section"

    section_id: Mapped[str] = mapped_column(String, primary_key=True)
    baseline_id: Mapped[str] = mapped_column(String, ForeignKey("baseline_assessment.baseline_id"))
    section_name: Mapped[str] = mapped_column(String)
    instructions: Mapped[str | None] = mapped_column(Text)
    order_index: Mapped[int] = mapped_column(Integer)
    target_defect_id: Mapped[str | None] = mapped_column(String, ForeignKey("defect.defect_id"), nullable=True)

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
    defect_phoneme_focus: Mapped[str | None] = mapped_column(String, nullable=True)
    image_keyword: Mapped[str | None] = mapped_column(String, nullable=True)
    reference_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str | None] = mapped_column(String, nullable=True)
    scoring_method: Mapped[str | None] = mapped_column(String, nullable=True)

    section: Mapped["BaselineSection"] = relationship("BaselineSection", back_populates="items")


class PatientBaselineResult(Base):
    __tablename__ = "patient_baseline_result"

    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient.patient_id"))
    baseline_id: Mapped[str] = mapped_column(String, ForeignKey("baseline_assessment.baseline_id"))
    therapist_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("therapist.therapist_id"))
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    assessed_on: Mapped[date] = mapped_column(Date)
    raw_score: Mapped[int | None] = mapped_column(Integer)
    percentile: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    severity_rating: Mapped[str | None] = mapped_column(String)
    notes: Mapped[str | None] = mapped_column(Text)


class BaselineItemResult(Base):
    __tablename__ = "baseline_item_result"

    item_result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    result_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient_baseline_result.result_id"))
    item_id: Mapped[str] = mapped_column(String, ForeignKey("baseline_item.item_id"))
    score_given: Mapped[int | None] = mapped_column(Integer)
    error_noted: Mapped[str | None] = mapped_column(Text)
    clinician_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class BaselineAttempt(Base):
    """Tracks one audio recording attempt for a single baseline_item within a baseline session."""
    __tablename__ = "baseline_attempt"

    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("session.session_id"))
    item_id: Mapped[str] = mapped_column(String, ForeignKey("baseline_item.item_id"))
    audio_file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    result: Mapped[str] = mapped_column(String, default="pending")  # pending | scored | failed
    ml_phoneme_accuracy: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    ml_word_accuracy: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    ml_fluency_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    ml_speech_rate_wpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ml_speech_rate_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    ml_confidence: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    dominant_emotion: Mapped[str | None] = mapped_column(String, nullable=True)
    emotion_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    engagement_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    asr_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    computed_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
