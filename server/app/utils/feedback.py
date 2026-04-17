"""Emotion-aware, empathetic feedback generator for speech therapy attempts."""

import random


# ---------------------------------------------------------------------------
# Message pools
# ---------------------------------------------------------------------------

_PASS_HIGH = [
    "Excellent work — that was a really strong attempt!",
    "You nailed it! That kind of effort really shows.",
    "That's the stuff! Your hard work is paying off.",
    "Brilliant — keep that momentum going!",
    "You're doing great. That was a confident, clear response.",
]

_PASS_MODERATE = [
    "Good job! You're making real progress.",
    "That worked well — you're on the right track.",
    "Nice effort! Each attempt builds your skills.",
    "Well done — you got through it and that counts.",
    "Solid attempt! You're finding your rhythm.",
]

_FAIL_GENTLE = [
    "That one was tricky — let's try it again together.",
    "Almost there! A small adjustment and you'll get it.",
    "No worries — this is what practice is for. Let's go again.",
    "Keep going — every try is teaching you something new.",
    "That's okay! The next attempt is a fresh start.",
]

_FAIL_STRUGGLING = [
    "This is genuinely hard work, and you're still showing up — that's what matters.",
    "You're working through something real here. Let's slow down and try again.",
    "Don't be hard on yourself — learning takes time and you're doing it.",
    "It's okay if this is tough right now. Take a breath and we'll go again.",
    "Progress isn't always linear. You're still here, and that's everything.",
]

_NO_SPEECH = [
    "Looks like we missed that one — let's fix it together!",
    "We didn't catch your voice that time. Ready to try again?",
    "No audio was picked up. Make sure the mic is clear and go for it!",
    "Seems like something went quiet there — let's give it another go.",
    "No speech detected this time. Take a moment and try again when you're ready.",
]

_DISTRESS_ANGRY_FEARFUL = [
    "You did the speech work — let's slow down for a moment before continuing.",
    "Take a breath. You've done something hard and you can take a pause.",
    "It's okay to feel frustrated. You're still here and that's real strength.",
    "Let's take this one step at a time. You're safe to go at your own pace.",
]

_DISTRESS_SAD = [
    "You are still making progress, even when it doesn't feel that way.",
    "Let's keep the next step gentle. You're doing better than you think.",
    "It's okay to have a hard day. You showed up and that matters a lot.",
    "You're not alone in this. Let's keep going at a comfortable pace.",
]

_STREAK_MILESTONE = {
    3:  ["3 days in a row — you're building a great habit!", "3-day streak! You're on your way."],
    5:  ["5 days straight — impressive consistency!", "High five! 5-day streak achieved."],
    7:  ["A full week! That's a huge milestone — well done.", "7 days in a row. You're unstoppable!"],
    10: ["10-day streak — you're really committed to this journey!", "Double digits! 10 days of showing up."],
    14: ["Two weeks of consistent practice — that's incredible!", "14-day streak! Your dedication is inspiring."],
    30: ["30 days! A whole month of showing up — you should be so proud.", "One month streak — remarkable dedication!"],
}

_STREAK_BROKEN = [
    "Every day is a fresh start. Let's build your streak again!",
    "That's okay — streaks can be rebuilt. Today is day one again!",
    "Missing a day happens. What matters is coming back, and here you are.",
    "Don't worry about yesterday. Today you showed up and that's all that counts.",
]

_ADVANCE = [
    "You've levelled up — your hard work earned it!",
    "Moving to the next level! You're ready for a new challenge.",
    "Level up! You've shown real mastery here.",
]

_DROP = [
    "We're adjusting to a level that fits better right now — that's smart practice.",
    "Let's work on a slightly easier challenge to build your confidence.",
    "Stepping back to solidify the foundations — that's how lasting progress happens.",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_friendly_feedback(
    pass_fail: str | None,
    adaptive_decision: str | None,
    dominant_emotion: str | None,
    emotion_score: float | None,
    final_score: float | None,
    fail_reason: str | None = None,
    current_streak: int = 0,
    no_speech: bool = False,
) -> str:
    """Return a warm, varied, emotion-aware feedback message."""

    # No-speech fast path
    is_retry_request = bool(fail_reason and "Please retry" in fail_reason)
    if no_speech or (
        not is_retry_request
        and pass_fail == "fail"
        and final_score == 0.0
        and not dominant_emotion
    ):
        return random.choice(_NO_SPEECH)

    emotion = (dominant_emotion or "").lower()
    e_score = float(emotion_score) if emotion_score is not None else 100.0
    score = float(final_score) if final_score is not None else 0.0

    # Distress override — emotion takes precedence over pass/fail
    is_distress_angry = emotion in ("angry", "fearful") and e_score <= 40
    is_distress_sad = emotion == "sad" and e_score <= 55

    if is_distress_angry:
        msg = random.choice(_DISTRESS_ANGRY_FEARFUL)
    elif is_distress_sad:
        msg = random.choice(_DISTRESS_SAD)
    elif pass_fail == "pass":
        msg = random.choice(_PASS_HIGH if score >= 80 else _PASS_MODERATE)
    elif pass_fail == "fail":
        # Distinguish struggling (low emotion + low score) from normal fail
        is_struggling = score < 45 or emotion in ("sad", "angry", "fearful")
        msg = random.choice(_FAIL_STRUGGLING if is_struggling else _FAIL_GENTLE)
    else:
        msg = random.choice(_PASS_MODERATE)

    # Append streak milestone if applicable (streak set to new value after update)
    if pass_fail == "pass" and current_streak > 0:
        milestone_msgs = _STREAK_MILESTONE.get(current_streak)
        if milestone_msgs:
            msg = random.choice(milestone_msgs)
        elif adaptive_decision == "advance":
            msg = random.choice(_ADVANCE)
    elif pass_fail == "pass" and adaptive_decision == "advance":
        msg = random.choice(_ADVANCE)
    elif adaptive_decision == "drop" and not is_distress_angry and not is_distress_sad:
        msg = random.choice(_DROP)

    return msg


def generate_streak_broken_feedback() -> str:
    return random.choice(_STREAK_BROKEN)
