from datetime import datetime, timezone
from sqlalchemy import String, Integer, Text, ForeignKey, Boolean, Numeric, TIMESTAMP, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Defect(Base):
    __tablename__ = "defect"

    defect_id: Mapped[str] = mapped_column(String, primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    age_group: Mapped[str] = mapped_column(String, default="child")
    description: Mapped[str | None] = mapped_column(Text)


class Task(Base):
    __tablename__ = "task"

    task_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String)
    task_mode: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text)
    ideal_wpm_min: Mapped[int] = mapped_column(Integer, default=80)
    ideal_wpm_max: Mapped[int] = mapped_column(Integer, default=120)
    wpm_tolerance: Mapped[int] = mapped_column(Integer, default=20)
    source_id: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))

    levels: Mapped[list["TaskLevel"]] = relationship("TaskLevel", back_populates="task")
    scoring_weights: Mapped["TaskScoringWeights | None"] = relationship("TaskScoringWeights", back_populates="task", uselist=False)


class TaskLevel(Base):
    __tablename__ = "task_level"

    level_id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(String, ForeignKey("task.task_id"))
    level_name: Mapped[str] = mapped_column(String)
    difficulty_score: Mapped[int] = mapped_column(Integer)
    source_level_id: Mapped[str | None] = mapped_column(String, nullable=True)

    task: Mapped["Task"] = relationship("Task", back_populates="levels")
    prompts: Mapped[list["Prompt"]] = relationship("Prompt", back_populates="level")


class Prompt(Base):
    __tablename__ = "prompt"

    prompt_id: Mapped[str] = mapped_column(String, primary_key=True)
    level_id: Mapped[str] = mapped_column(String, ForeignKey("task_level.level_id"))
    prompt_type: Mapped[str] = mapped_column(String, default="exercise")
    task_mode: Mapped[str] = mapped_column(String)
    scenario_context: Mapped[str | None] = mapped_column(Text)
    instruction: Mapped[str | None] = mapped_column(Text)
    display_content: Mapped[str | None] = mapped_column(Text)
    target_response: Mapped[str | None] = mapped_column(Text)
    accuracy_check: Mapped[str | None] = mapped_column(Text)
    evaluation_criteria: Mapped[str | None] = mapped_column(String)
    source_prompt_id: Mapped[str | None] = mapped_column(String, nullable=True)

    # Merged from speech_target
    speech_target: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Merged from evaluation_target
    eval_scope: Mapped[str | None] = mapped_column(String, nullable=True)
    target_phonemes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Merged from feedback_rule
    pass_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    partial_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    fail_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Merged from prompt_scoring
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    tc_mode: Mapped[str | None] = mapped_column(String, nullable=True)
    target_word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_length_words: Mapped[int | None] = mapped_column(Integer, nullable=True)
    aq_relevance_threshold: Mapped[float] = mapped_column(Numeric, default=0.60)

    level: Mapped["TaskLevel"] = relationship("TaskLevel", back_populates="prompts")
    adaptive_threshold: Mapped["AdaptiveThreshold | None"] = relationship("AdaptiveThreshold", back_populates="prompt", uselist=False)


class TaskDefectMapping(Base):
    __tablename__ = "task_defect_mapping"
    __table_args__ = (UniqueConstraint("task_id", "defect_id"),)

    mapping_id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(String, ForeignKey("task.task_id"))
    defect_id: Mapped[str] = mapped_column(String, ForeignKey("defect.defect_id"))
    relevance_level: Mapped[str | None] = mapped_column(String, nullable=True)
    clinical_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class TaskScoringWeights(Base):
    __tablename__ = "task_scoring_weights"

    weight_id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(String, ForeignKey("task.task_id"), unique=True)
    speech_w_pa: Mapped[float] = mapped_column(Numeric, default=0.40)
    speech_w_wa: Mapped[float] = mapped_column(Numeric, default=0.30)
    speech_w_fs: Mapped[float] = mapped_column(Numeric, default=0.15)
    speech_w_srs: Mapped[float] = mapped_column(Numeric, default=0.10)
    speech_w_cs: Mapped[float] = mapped_column(Numeric, default=0.05)
    fusion_w_speech: Mapped[float] = mapped_column(Numeric, default=0.90)
    fusion_w_engagement: Mapped[float] = mapped_column(Numeric, default=0.10)
    engagement_w_emotion: Mapped[float] = mapped_column(Numeric, default=0.65)
    engagement_w_behavioral: Mapped[float] = mapped_column(Numeric, default=0.35)
    behavioral_w_rl: Mapped[float] = mapped_column(Numeric, default=0.40)
    behavioral_w_tc: Mapped[float] = mapped_column(Numeric, default=0.35)
    behavioral_w_aq: Mapped[float] = mapped_column(Numeric, default=0.25)
    adaptive_advance_threshold: Mapped[float] = mapped_column(Numeric, default=75.0)
    adaptive_stay_min: Mapped[float] = mapped_column(Numeric, default=55.0)
    adaptive_stay_max: Mapped[float] = mapped_column(Numeric, default=74.0)
    adaptive_drop_threshold: Mapped[float] = mapped_column(Numeric, default=55.0)
    adaptive_consecutive_fail_limit: Mapped[int] = mapped_column(Integer, default=3)
    adaptive_advance_lookback_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    adaptive_advance_lookback_threshold: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    adaptive_consecutive_fail_ceiling: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rule_severe_pa_threshold: Mapped[float] = mapped_column(Numeric, default=35.0)
    rule_severe_pa_score_cap: Mapped[float] = mapped_column(Numeric, default=45.0)
    rule_low_eng_threshold: Mapped[float] = mapped_column(Numeric, default=35.0)
    rule_low_eng_penalty: Mapped[float] = mapped_column(Numeric, default=5.0)
    rule_high_eng_threshold: Mapped[float] = mapped_column(Numeric, default=85.0)
    rule_high_eng_boost: Mapped[float] = mapped_column(Numeric, default=5.0)
    rule_low_conf_threshold: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    task: Mapped["Task"] = relationship("Task", back_populates="scoring_weights")


class AdaptiveThreshold(Base):
    __tablename__ = "adaptive_threshold"

    threshold_id: Mapped[str] = mapped_column(String, primary_key=True)
    prompt_id: Mapped[str] = mapped_column(String, ForeignKey("prompt.prompt_id"), unique=True)
    advance_to_next_level: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    stay_at_current_level_min: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    stay_at_current_level_max: Mapped[float | None] = mapped_column(Numeric, nullable=True)

    prompt: Mapped["Prompt"] = relationship("Prompt", back_populates="adaptive_threshold")


class DefectPAThreshold(Base):
    __tablename__ = "defect_pa_threshold"

    threshold_id: Mapped[str] = mapped_column(String, primary_key=True)
    defect_id: Mapped[str] = mapped_column(String, ForeignKey("defect.defect_id"))
    min_pa_to_pass: Mapped[float] = mapped_column(Numeric)
    target_phonemes: Mapped[list | None] = mapped_column(ARRAY(String), nullable=True)
    phoneme_scope: Mapped[str | None] = mapped_column(String, nullable=True)
    severity_modifier: Mapped[float] = mapped_column(Numeric, default=1.0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))


class EmotionWeightsConfig(Base):
    __tablename__ = "emotion_weights_config"

    config_id: Mapped[str] = mapped_column(String, primary_key=True)
    age_group: Mapped[str] = mapped_column(String, unique=True)
    w_happy: Mapped[float] = mapped_column(Numeric, default=0)
    w_excited: Mapped[float] = mapped_column(Numeric, default=0)
    w_neutral: Mapped[float] = mapped_column(Numeric, default=0)
    w_surprised: Mapped[float] = mapped_column(Numeric, default=0)
    w_sad: Mapped[float] = mapped_column(Numeric, default=0)
    w_angry: Mapped[float] = mapped_column(Numeric, default=0)
    w_fearful: Mapped[float] = mapped_column(Numeric, default=0)
    w_positive_affect: Mapped[float] = mapped_column(Numeric, default=0)
    w_focused: Mapped[float] = mapped_column(Numeric, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
