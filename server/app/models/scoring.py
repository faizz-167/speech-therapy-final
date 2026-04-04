import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, Boolean, Numeric, ForeignKey, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Session(Base):
    __tablename__ = "session"
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("therapy_plan.plan_id"), nullable=True)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient.patient_id"))
    therapist_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("therapist.therapist_id"), nullable=True)
    session_date: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    session_type: Mapped[str] = mapped_column(String, default="therapy")
    session_notes: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[list["SessionPromptAttempt"]] = relationship("SessionPromptAttempt", back_populates="session")


class SessionPromptAttempt(Base):
    __tablename__ = "session_prompt_attempt"
    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("session.session_id"))
    prompt_id: Mapped[str] = mapped_column(String, ForeignKey("prompt.prompt_id"))
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    result: Mapped[str | None] = mapped_column(String)
    accuracy_score: Mapped[float | None] = mapped_column(Numeric)
    asr_transcript: Mapped[str | None] = mapped_column(Text)
    audio_file_path: Mapped[str | None] = mapped_column(String)
    task_mode: Mapped[str | None] = mapped_column(String)
    prompt_type: Mapped[str | None] = mapped_column(String)
    speech_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    mic_activated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    speech_start_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    session: Mapped["Session"] = relationship("Session", back_populates="attempts")
    score_detail: Mapped["AttemptScoreDetail | None"] = relationship("AttemptScoreDetail", back_populates="attempt", uselist=False)


class AttemptScoreDetail(Base):
    __tablename__ = "attempt_score_detail"
    detail_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("session_prompt_attempt.attempt_id"), unique=True)
    word_accuracy: Mapped[float | None] = mapped_column(Numeric)
    phoneme_accuracy: Mapped[float | None] = mapped_column(Numeric)
    fluency_score: Mapped[float | None] = mapped_column(Numeric)
    disfluency_rate: Mapped[float | None] = mapped_column(Numeric)
    pause_score: Mapped[float | None] = mapped_column(Numeric)
    speech_rate_wpm: Mapped[int | None] = mapped_column(Integer)
    speech_rate_score: Mapped[float | None] = mapped_column(Numeric)
    confidence_score: Mapped[float | None] = mapped_column(Numeric)
    rl_score: Mapped[float | None] = mapped_column(Numeric)
    tc_score: Mapped[float | None] = mapped_column(Numeric)
    aq_score: Mapped[float | None] = mapped_column(Numeric)
    behavioral_score: Mapped[float | None] = mapped_column(Numeric)
    dominant_emotion: Mapped[str | None] = mapped_column(String)
    emotion_score: Mapped[float | None] = mapped_column(Numeric)
    engagement_score: Mapped[float | None] = mapped_column(Numeric)
    speech_score: Mapped[float | None] = mapped_column(Numeric)
    final_score: Mapped[float | None] = mapped_column(Numeric)
    adaptive_decision: Mapped[str | None] = mapped_column(String)
    pass_fail: Mapped[str | None] = mapped_column(String)
    fail_reason: Mapped[str | None] = mapped_column(Text)
    performance_level: Mapped[str | None] = mapped_column(String)
    baseline_score_ref: Mapped[float | None] = mapped_column(Numeric)
    progress_delta: Mapped[float | None] = mapped_column(Numeric)
    progress_classification: Mapped[str | None] = mapped_column(String)
    low_confidence_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    review_recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    warmup_gate_passed: Mapped[bool | None] = mapped_column(Boolean)
    target_phoneme_results: Mapped[dict | None] = mapped_column(JSONB)
    asr_transcript: Mapped[str | None] = mapped_column(Text)
    audio_duration_sec: Mapped[float | None] = mapped_column(Numeric)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    attempt: Mapped["SessionPromptAttempt"] = relationship("SessionPromptAttempt", back_populates="score_detail")


class PatientTaskProgress(Base):
    __tablename__ = "patient_task_progress"
    progress_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient.patient_id"))
    task_id: Mapped[str] = mapped_column(String, ForeignKey("task.task_id"))
    current_level_id: Mapped[str | None] = mapped_column(String, ForeignKey("task_level.level_id"))
    consecutive_passes: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_fails: Mapped[int] = mapped_column(Integer, default=0)
    overall_accuracy: Mapped[float | None] = mapped_column(Numeric)
    last_final_score: Mapped[float | None] = mapped_column(Numeric)
    baseline_score: Mapped[float | None] = mapped_column(Numeric)
    total_attempts: Mapped[int] = mapped_column(Integer, default=0)
    sessions_at_level: Mapped[int] = mapped_column(Integer, default=0)
    level_locked_until: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    last_attempted_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))


class SessionEmotionSummary(Base):
    __tablename__ = "session_emotion_summary"
    summary_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("session.session_id"))
    patient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patient.patient_id"))
    session_date: Mapped[str | None] = mapped_column(String)
    dominant_emotion: Mapped[str | None] = mapped_column(String)
    avg_frustration: Mapped[float | None] = mapped_column(Numeric)
    avg_engagement: Mapped[float | None] = mapped_column(Numeric)
    drop_count: Mapped[int] = mapped_column(Integer, default=0)
