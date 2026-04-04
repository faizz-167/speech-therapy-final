from dataclasses import dataclass
from typing import Optional


@dataclass
class ScoringWeights:
    speech_w_pa: float = 0.40
    speech_w_wa: float = 0.30
    speech_w_fs: float = 0.15
    speech_w_srs: float = 0.10
    speech_w_cs: float = 0.05
    fusion_w_speech: float = 0.90
    fusion_w_engagement: float = 0.10
    engagement_w_emotion: float = 0.65
    engagement_w_behavioral: float = 0.35
    behavioral_w_rl: float = 0.40
    behavioral_w_tc: float = 0.35
    behavioral_w_aq: float = 0.25
    adaptive_advance_threshold: float = 75.0
    adaptive_stay_min: float = 55.0
    adaptive_drop_threshold: float = 55.0
    adaptive_consecutive_fail_limit: int = 3
    rule_low_eng_threshold: float = 35.0
    rule_low_eng_penalty: float = 5.0
    rule_high_eng_threshold: float = 85.0
    rule_high_eng_boost: float = 5.0
    rule_severe_pa_threshold: float = 35.0
    rule_severe_pa_score_cap: float = 45.0


def score_attempt(
    pa: float,
    wa: float,
    fs: float,
    srs: float,
    cs: float,
    rl_score: float,
    tc_score: float,
    aq_score: float,
    emotion_score: float,
    weights: Optional[ScoringWeights] = None,
) -> dict:
    """
    Compute final score using formula v2.
    All inputs are 0–100 scale.
    Returns a dict with all intermediate and final scores + adaptive decision.
    """
    if weights is None:
        weights = ScoringWeights()

    speech_score = (
        pa * weights.speech_w_pa
        + wa * weights.speech_w_wa
        + fs * weights.speech_w_fs
        + srs * weights.speech_w_srs
        + cs * weights.speech_w_cs
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

    if pa < weights.rule_severe_pa_threshold:
        final_score = min(final_score, weights.rule_severe_pa_score_cap)
    if engagement_score < weights.rule_low_eng_threshold:
        final_score -= weights.rule_low_eng_penalty
    elif engagement_score > weights.rule_high_eng_threshold:
        final_score += weights.rule_high_eng_boost

    final_score = min(100.0, max(0.0, final_score))

    if final_score >= weights.adaptive_advance_threshold:
        adaptive_decision = "advance"
        pass_fail = "pass"
        performance_level = "advanced"
    elif final_score >= weights.adaptive_stay_min:
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
