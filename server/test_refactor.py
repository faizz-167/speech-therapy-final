"""Quick smoke test for refactored modules."""
import sys
sys.path.insert(0, ".")

from app.constants import MAX_ATTEMPTS_PER_PROMPT, ESCALATION_INTERVENTION_LIMIT
from app.enums import PassFail, AdaptiveDecision
from app.tasks.scoring_helpers import (
    compute_word_accuracy, compute_speech_rate_wpm, compute_speech_rate_score,
    is_no_speech, as_float, as_int, compute_rl_score, compute_tc_score,
    compute_aq_score, parse_target_phonemes, to_builtin,
    score_clinical_emotion, apply_emotion_priority_override,
)

# Constants
assert MAX_ATTEMPTS_PER_PROMPT == 3
assert ESCALATION_INTERVENTION_LIMIT == 2
print("[OK] constants.py")

# Enums
assert PassFail.PASS.value == "pass"
assert AdaptiveDecision.ESCALATED.value == "escalated"
print("[OK] enums.py")

# Type coercion
assert as_float(None) == 0.0
assert as_float(42.5) == 42.5
assert as_int(None) == 0
assert as_int(3.7) == 3
assert to_builtin(99) == 99
print("[OK] type coercion")

# Word accuracy
assert compute_word_accuracy("the cat sat", "the cat sat on mat") == 60.0
assert compute_word_accuracy("", "hello") == 0.0
assert compute_word_accuracy("hello", "") == 0.0
print("[OK] compute_word_accuracy")

# Speech rate
wpm = compute_speech_rate_wpm("hello world foo bar", 2.0)
assert wpm > 0
score = compute_speech_rate_score(100)  # within ideal range
assert score == 100.0
print("[OK] compute_speech_rate_wpm/score")

# No-speech detection
assert is_no_speech("", 0.5, 0.1) is True
assert is_no_speech("hello world how are you", 3.0, 0.9) is False
print("[OK] is_no_speech")

# RL, TC, AQ scores
assert 0 <= compute_rl_score(None, None) <= 100
assert 0 <= compute_tc_score("hello world", None, None, 2.0) <= 100
assert 0 <= compute_aq_score("hello") <= 100
print("[OK] rl/tc/aq scores")

# Phoneme parsing
assert parse_target_phonemes(None) == []
assert parse_target_phonemes("a, b, c") == ["a", "b", "c"]
assert parse_target_phonemes({"phonemes": ["p", "t"]}) == ["p", "t"]
print("[OK] parse_target_phonemes")

# Clinical emotion scoring
result = score_clinical_emotion({"dominant_emotion": "happy", "emotion_score": 90.0}, "child")
assert result is not None and result > 0
print("[OK] score_clinical_emotion")

# Emotion priority override
scores = {"adaptive_decision": "advance", "performance_level": "advanced"}
overridden = apply_emotion_priority_override(scores, "angry", 30.0)
assert overridden["adaptive_decision"] == "stay"
assert overridden["performance_level"] == "support_needed"
print("[OK] apply_emotion_priority_override")

print("\n=== ALL SMOKE TESTS PASSED ===")
