from sqlalchemy import String, Integer, Text, ForeignKey, Boolean, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Defect(Base):
    __tablename__ = "defect"
    defect_id: Mapped[str] = mapped_column(String, primary_key=True)
    code: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
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
    levels: Mapped[list["TaskLevel"]] = relationship("TaskLevel", back_populates="task")
    scoring_weights: Mapped["TaskScoringWeights | None"] = relationship("TaskScoringWeights", back_populates="task", uselist=False)


class TaskLevel(Base):
    __tablename__ = "task_level"
    level_id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(String, ForeignKey("task.task_id"))
    level_name: Mapped[str] = mapped_column(String)
    difficulty_score: Mapped[int] = mapped_column(Integer)
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
    level: Mapped["TaskLevel"] = relationship("TaskLevel", back_populates="prompts")
    speech_target: Mapped["SpeechTarget | None"] = relationship("SpeechTarget", back_populates="prompt", uselist=False)
    evaluation_target: Mapped["EvaluationTarget | None"] = relationship("EvaluationTarget", back_populates="prompt", uselist=False)
    feedback_rule: Mapped["FeedbackRule | None"] = relationship("FeedbackRule", back_populates="prompt", uselist=False)
    prompt_scoring: Mapped["PromptScoring | None"] = relationship("PromptScoring", back_populates="prompt", uselist=False)


class SpeechTarget(Base):
    __tablename__ = "speech_target"
    speech_target_id: Mapped[str] = mapped_column(String, primary_key=True)
    prompt_id: Mapped[str] = mapped_column(String, ForeignKey("prompt.prompt_id"), unique=True)
    raw_speech_target: Mapped[dict | None] = mapped_column(JSONB)
    prompt: Mapped["Prompt"] = relationship("Prompt", back_populates="speech_target")


class EvaluationTarget(Base):
    __tablename__ = "evaluation_target"
    eval_target_id: Mapped[str] = mapped_column(String, primary_key=True)
    prompt_id: Mapped[str] = mapped_column(String, ForeignKey("prompt.prompt_id"), unique=True)
    scope: Mapped[str | None] = mapped_column(String)
    target_phonemes: Mapped[dict | None] = mapped_column(JSONB)
    prompt: Mapped["Prompt"] = relationship("Prompt", back_populates="evaluation_target")


class FeedbackRule(Base):
    __tablename__ = "feedback_rule"
    feedback_id: Mapped[str] = mapped_column(String, primary_key=True)
    prompt_id: Mapped[str] = mapped_column(String, ForeignKey("prompt.prompt_id"), unique=True)
    pass_message: Mapped[str | None] = mapped_column(Text)
    partial_message: Mapped[str | None] = mapped_column(Text)
    fail_message: Mapped[str | None] = mapped_column(Text)
    prompt: Mapped["Prompt"] = relationship("Prompt", back_populates="feedback_rule")


class PromptScoring(Base):
    __tablename__ = "prompt_scoring"
    scoring_id: Mapped[str] = mapped_column(String, primary_key=True)
    prompt_id: Mapped[str] = mapped_column(String, ForeignKey("prompt.prompt_id"), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    tc_mode: Mapped[str | None] = mapped_column(String)
    target_word_count: Mapped[int | None] = mapped_column(Integer)
    target_duration_sec: Mapped[int | None] = mapped_column(Integer)
    min_length_words: Mapped[int | None] = mapped_column(Integer)
    aq_relevance_threshold: Mapped[float] = mapped_column(Numeric, default=0.60)
    prompt: Mapped["Prompt"] = relationship("Prompt", back_populates="prompt_scoring")


class TaskDefectMapping(Base):
    __tablename__ = "task_defect_mapping"
    mapping_id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(String, ForeignKey("task.task_id"))
    defect_id: Mapped[str] = mapped_column(String, ForeignKey("defect.defect_id"))
    relevance_level: Mapped[str | None] = mapped_column(String)


class TaskScoringWeights(Base):
    __tablename__ = "task_scoring_weights"
    weight_id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(String, ForeignKey("task.task_id"), unique=True)
    speech_w_pa: Mapped[float] = mapped_column(Numeric, default=0)
    speech_w_wa: Mapped[float] = mapped_column(Numeric, default=0)
    speech_w_fs: Mapped[float] = mapped_column(Numeric, default=0)
    speech_w_srs: Mapped[float] = mapped_column(Numeric, default=0)
    speech_w_cs: Mapped[float] = mapped_column(Numeric, default=0)
    fusion_w_speech: Mapped[float] = mapped_column(Numeric, default=0.9)
    fusion_w_engagement: Mapped[float] = mapped_column(Numeric, default=0.1)
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
    rule_low_eng_threshold: Mapped[float] = mapped_column(Numeric, default=35.0)
    rule_low_eng_penalty: Mapped[float] = mapped_column(Numeric, default=5.0)
    rule_high_eng_threshold: Mapped[float] = mapped_column(Numeric, default=85.0)
    rule_high_eng_boost: Mapped[float] = mapped_column(Numeric, default=5.0)
    rule_severe_pa_threshold: Mapped[float] = mapped_column(Numeric, default=35.0)
    rule_severe_pa_score_cap: Mapped[float] = mapped_column(Numeric, default=45.0)
    task: Mapped["Task"] = relationship("Task", back_populates="scoring_weights")
