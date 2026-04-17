"""Pure scoring and computation helpers extracted from the analysis task.

Every function here is stateless — no DB, no Redis, no side effects.
"""

from datetime import datetime
from numbers import Number

from app.constants import (
    ASR_LOW_CONFIDENCE_THRESHOLD,
    DEFAULT_IDEAL_WPM_MAX,
    DEFAULT_IDEAL_WPM_MIN,
    DEFAULT_WPM_TOLERANCE,
    NO_SPEECH_CONFIDENCE_FLOOR,
    NO_SPEECH_MIN_DURATION,
)


# ---------------------------------------------------------------------------
# Type coercion helpers
# ---------------------------------------------------------------------------

def to_builtin(value):
    """Convert numpy/torch scalar to Python builtin."""
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def as_float(value, default: float = 0.0) -> float:
    value = to_builtin(value)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value, default: int = 0) -> int:
    value = to_builtin(value)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Word / transcript analysis
# ---------------------------------------------------------------------------

_PUNCTUATION = ".,!?;:\"'()[]{}"


def compute_word_accuracy(transcript: str, target_text: str) -> float:
    if not target_text or not transcript:
        return 0.0
    target_words = {
        word.strip(_PUNCTUATION).lower()
        for word in target_text.split()
        if word.strip(_PUNCTUATION)
    }
    spoken_words = {
        word.strip(_PUNCTUATION).lower()
        for word in transcript.split()
        if word.strip(_PUNCTUATION)
    }
    if not target_words:
        return 0.0
    matches = target_words & spoken_words
    return round((len(matches) / len(target_words)) * 100, 2)


def is_no_speech(transcript: str, duration: float, avg_confidence: float) -> bool:
    normalized = transcript.strip()
    if not normalized:
        return True
    word_count = len(normalized.split())
    if word_count == 0:
        return True
    return (
        word_count <= 1
        and duration < NO_SPEECH_MIN_DURATION
        and avg_confidence < NO_SPEECH_CONFIDENCE_FLOOR
    )


def needs_asr_review(
    transcript: str,
    target_text: str | None,
    avg_confidence: float,
    word_accuracy: float,
) -> bool:
    if avg_confidence < ASR_LOW_CONFIDENCE_THRESHOLD:
        return True
    if not transcript.strip():
        return True
    if target_text and word_accuracy == 0.0 and len(transcript.split()) >= 3:
        return True
    return False


# ---------------------------------------------------------------------------
# Speech rate
# ---------------------------------------------------------------------------

def compute_speech_rate_wpm(
    transcript: str,
    duration: float,
    words: list[dict] | None = None,
) -> float:
    word_count = len(transcript.split())
    if word_count == 0:
        return 0.0

    timed_words = [
        w for w in (words or [])
        if w.get("start") is not None and w.get("end") is not None
    ]
    if len(timed_words) >= 2:
        speech_span = float(timed_words[-1]["end"]) - float(timed_words[0]["start"])
    elif len(timed_words) == 1:
        speech_span = float(timed_words[0]["end"]) - float(timed_words[0]["start"])
    else:
        speech_span = duration

    speech_span = max(0.5, speech_span)
    return (word_count / speech_span) * 60


def compute_speech_rate_score(
    wpm: float,
    ideal_min: int = DEFAULT_IDEAL_WPM_MIN,
    ideal_max: int = DEFAULT_IDEAL_WPM_MAX,
    tolerance: int = DEFAULT_WPM_TOLERANCE,
) -> float:
    if wpm <= 0:
        return 0.0
    tolerance = max(1, tolerance)
    if ideal_min <= wpm <= ideal_max:
        return 100.0

    diff = (ideal_min - wpm) if wpm < ideal_min else (wpm - ideal_max)
    if diff <= tolerance:
        return round(100.0 - ((diff / tolerance) * 25.0), 2)
    if diff <= tolerance * 2:
        return round(75.0 - (((diff - tolerance) / tolerance) * 35.0), 2)
    return round(max(0.0, 40.0 - (((diff - (tolerance * 2)) / (tolerance * 2)) * 40.0)), 2)


# ---------------------------------------------------------------------------
# Response latency / task completion / answer quality
# ---------------------------------------------------------------------------

def compute_rl_score(mic_at: str | None, speech_at: str | None) -> float:
    if not mic_at or not speech_at:
        return 70.0
    try:
        latency = (
            datetime.fromisoformat(speech_at) - datetime.fromisoformat(mic_at)
        ).total_seconds()
        if latency <= 1.0:
            return 100.0
        if latency <= 3.0:
            return 80.0
        if latency <= 5.0:
            return 60.0
        return 40.0
    except Exception:
        return 70.0


def compute_tc_score(
    transcript: str,
    target_word_count: int | None,
    target_duration: float | None,
    duration: float,
) -> float:
    if target_word_count:
        spoken = len(transcript.split())
        ratio = min(spoken / target_word_count, 1.0)
        return round(ratio * 100, 2)
    if target_duration and duration > 0:
        ratio = min(duration / target_duration, 1.0)
        return round(ratio * 100, 2)
    return 80.0


def compute_aq_score(transcript: str) -> float:
    words = transcript.strip().split()
    if len(words) < 2:
        return 30.0
    if len(words) < 5:
        return 60.0
    return 85.0


# ---------------------------------------------------------------------------
# Phoneme parsing
# ---------------------------------------------------------------------------

def parse_target_phonemes(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, dict):
        phonemes = value.get("phonemes") or value.get("target_sounds") or []
        return [str(item) for item in phonemes if item]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


# ---------------------------------------------------------------------------
# Emotion scoring
# ---------------------------------------------------------------------------

CLINICAL_EMOTION_BASE_SCORES = {
    "child": {"happy": 95.0, "neutral": 80.0, "sad": 50.0, "angry": 35.0},
    "adult": {"happy": 85.0, "neutral": 90.0, "sad": 50.0, "angry": 35.0},
    "senior": {"happy": 85.0, "neutral": 90.0, "sad": 50.0, "angry": 35.0},
}


def score_clinical_emotion(emotion_result: dict, age_group: str) -> float | None:
    dominant_emotion = str(emotion_result.get("dominant_emotion") or "").lower()
    age_scores = CLINICAL_EMOTION_BASE_SCORES.get(age_group) or CLINICAL_EMOTION_BASE_SCORES["adult"]
    if dominant_emotion not in age_scores:
        return None
    raw_emotion_score = as_float(emotion_result.get("emotion_score"))
    confidence = as_float(emotion_result.get("confidence"), default=raw_emotion_score / 100.0)
    confidence = min(1.0, max(0.0, confidence))
    return round(min(100.0, max(0.0, age_scores[dominant_emotion] * confidence)), 2)


def build_emotion_weight_map(row) -> dict[str, float]:
    if not row:
        return {}
    return {
        "happy": as_float(row[0]),
        "excited": as_float(row[1]),
        "neutral": as_float(row[2]),
        "surprised": as_float(row[3]),
        "sad": as_float(row[4]),
        "angry": as_float(row[5]),
        "fearful": as_float(row[6]),
        "positive_affect": as_float(row[7]),
        "focused": as_float(row[8]),
    }


def score_emotion_with_config(
    emotion_result: dict,
    emotion_weights_row,
    age_group: str = "adult",
) -> float:
    raw_emotion_score = as_float(emotion_result.get("emotion_score"))
    dominant_emotion = emotion_result.get("dominant_emotion")
    clinical_score = score_clinical_emotion(emotion_result, age_group)
    if clinical_score is not None:
        return clinical_score

    if not dominant_emotion or emotion_weights_row is None:
        return raw_emotion_score

    weights = build_emotion_weight_map(emotion_weights_row)
    if not weights:
        return raw_emotion_score

    confidence = as_float(emotion_result.get("confidence"), default=raw_emotion_score / 100.0)

    def _weighted_capacity(emotion_name: str) -> float:
        score = weights.get(emotion_name, 0.0)
        if emotion_name in {"happy", "excited", "surprised"}:
            score += weights.get("positive_affect", 0.0)
        if emotion_name == "neutral":
            score += weights.get("focused", 0.0)
        return score

    numerator = _weighted_capacity(dominant_emotion)
    denominator = max(
        (_weighted_capacity(name) for name in ("happy", "excited", "neutral", "surprised", "sad", "angry", "fearful")),
        default=0.0,
    )
    if denominator <= 0.0:
        return raw_emotion_score
    weighted_score = confidence * (numerator / denominator) * 100.0
    return round(min(100.0, max(0.0, weighted_score)), 2)


def apply_emotion_priority_override(
    scores: dict,
    dominant_emotion: str | None,
    emotion_score: float,
) -> dict:
    normalized_emotion = str(dominant_emotion or "").strip().lower()
    updated = dict(scores)

    if normalized_emotion in {"angry", "fearful"} and emotion_score <= 40.0:
        if updated.get("adaptive_decision") == "advance":
            updated["adaptive_decision"] = "stay"
        updated["performance_level"] = "support_needed"
        return updated

    if normalized_emotion == "sad" and emotion_score <= 55.0:
        if updated.get("adaptive_decision") == "advance":
            updated["adaptive_decision"] = "stay"
        if updated.get("performance_level") == "advanced":
            updated["performance_level"] = "support_needed"
        return updated

    return updated
