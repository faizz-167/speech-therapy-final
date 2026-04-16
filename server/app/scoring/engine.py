from dataclasses import dataclass
from typing import Optional


@dataclass
class ScoringWeights:
    speech_w_pa: float = 0.40
    speech_w_wa: float = 0.30
    speech_w_fs: float = 0.15
    speech_w_srs: float = 0.10
    speech_w_cs: float = 0.05
    fusion_w_speech: float = 0.60
    fusion_w_engagement: float = 0.40
    engagement_w_emotion: float = 1.00
    engagement_w_behavioral: float = 0.00
    behavioral_w_rl: float = 0.40
    behavioral_w_tc: float = 0.35
    behavioral_w_aq: float = 0.25
    adaptive_advance_threshold: float = 75.0
    adaptive_stay_min: float = 60.0
    adaptive_drop_threshold: float = 60.0
    adaptive_consecutive_fail_limit: int = 3
    rule_low_eng_threshold: float = 35.0
    rule_low_eng_penalty: float = 5.0
    rule_high_eng_threshold: float = 85.0
    rule_high_eng_boost: float = 5.0
    rule_severe_pa_threshold: float = 35.0
    rule_severe_pa_score_cap: float = 45.0
    rule_low_conf_threshold: float = 0.50   # Whisper ASR quality gate
    adaptive_stay_max: float = 74.0         # Stay range ceiling


def _weighted_score(components: list[tuple[float, float, bool]]) -> float:
    active = [(value, weight) for value, weight, available in components if available and weight > 0]
    if not active:
        return 0.0
    total_weight = sum(weight for _, weight in active)
    if total_weight <= 0:
        return 0.0
    return sum(value * weight for value, weight in active) / total_weight


def weights_from_db_row(row) -> "ScoringWeights":
    """Convert a TaskScoringWeights ORM row to ScoringWeights dataclass."""
    return ScoringWeights(
        speech_w_pa=float(row.speech_w_pa),
        speech_w_wa=float(row.speech_w_wa),
        speech_w_fs=float(row.speech_w_fs),
        speech_w_srs=float(row.speech_w_srs),
        speech_w_cs=float(row.speech_w_cs),
        fusion_w_speech=float(row.fusion_w_speech),
        fusion_w_engagement=float(row.fusion_w_engagement),
        engagement_w_emotion=float(row.engagement_w_emotion),
        engagement_w_behavioral=float(row.engagement_w_behavioral),
        behavioral_w_rl=float(row.behavioral_w_rl),
        behavioral_w_tc=float(row.behavioral_w_tc),
        behavioral_w_aq=float(row.behavioral_w_aq),
        adaptive_advance_threshold=float(row.adaptive_advance_threshold),
        adaptive_stay_min=60.0,
        adaptive_drop_threshold=60.0,
        adaptive_consecutive_fail_limit=int(row.adaptive_consecutive_fail_limit),
        rule_low_eng_threshold=float(row.rule_low_eng_threshold),
        rule_low_eng_penalty=float(row.rule_low_eng_penalty),
        rule_high_eng_threshold=float(row.rule_high_eng_threshold),
        rule_high_eng_boost=float(row.rule_high_eng_boost),
        rule_severe_pa_threshold=float(row.rule_severe_pa_threshold),
        rule_severe_pa_score_cap=float(row.rule_severe_pa_score_cap),
        rule_low_conf_threshold=float(row.rule_low_conf_threshold) if row.rule_low_conf_threshold is not None else 0.50,
        adaptive_stay_max=74.0,
    )


def score_attempt(
    pa: float | None,
    wa: float,
    fs: float,
    srs: float,
    cs: float,
    rl_score: float,
    tc_score: float,
    aq_score: float,
    emotion_score: float,
    pa_available: bool = True,
    wa_available: bool = True,
    weights: Optional[ScoringWeights] = None,
) -> dict:
    """
    Compute final score using formula v2.
    All inputs are 0–100 scale.
    Returns a dict with all intermediate and final scores + adaptive decision.
    """
    if weights is None:
        weights = ScoringWeights()

    speech_score = _weighted_score(
        [
            (pa if pa is not None else 0.0, weights.speech_w_pa, pa_available),
            (wa, weights.speech_w_wa, wa_available),
            (fs, weights.speech_w_fs, True),
            (srs, weights.speech_w_srs, True),
            (cs, weights.speech_w_cs, True),
        ]
    )
    speech_score = min(100.0, max(0.0, speech_score))

    behavioral_score = (
        rl_score * weights.behavioral_w_rl
        + tc_score * weights.behavioral_w_tc
        + aq_score * weights.behavioral_w_aq
    )
    behavioral_score = min(100.0, max(0.0, behavioral_score))

    engagement_score = (
        emotion_score * weights.engagement_w_emotion
        + behavioral_score * weights.engagement_w_behavioral
    )
    engagement_score = min(100.0, max(0.0, engagement_score))

    final_score = (
        speech_score * weights.fusion_w_speech
        + engagement_score * weights.fusion_w_engagement
    )

    if pa_available and pa is not None and pa < weights.rule_severe_pa_threshold:
        final_score = min(final_score, weights.rule_severe_pa_score_cap)
    if engagement_score < weights.rule_low_eng_threshold:
        final_score -= weights.rule_low_eng_penalty
    elif engagement_score > weights.rule_high_eng_threshold:
        final_score += weights.rule_high_eng_boost

    final_score = min(100.0, max(0.0, final_score))

    if final_score >= 75.0:
        adaptive_decision = "advance"
        pass_fail = "pass"
        performance_level = "advanced"
    elif final_score >= 60.0:
        adaptive_decision = "stay"
        pass_fail = "pass"
        performance_level = "satisfactory"
    else:
        adaptive_decision = "drop"
        pass_fail = "fail"
        performance_level = "needs_improvement"

    return {
        "speech_score": round(speech_score, 2),
        "behavioral_score": round(behavioral_score, 2),
        "engagement_score": round(engagement_score, 2),
        "final_score": round(final_score, 2),
        "adaptive_decision": adaptive_decision,
        "pass_fail": pass_fail,
        "performance_level": performance_level,
    }
