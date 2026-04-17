"""Database persistence and WebSocket event publishing for scored attempts.

Groups all side-effecting operations: score detail inserts, progress upserts,
emotion summaries, review notifications, and Redis WS publishing.
"""

import json
import uuid
from collections import Counter
from datetime import date

import redis

from app.config import settings


# ---------------------------------------------------------------------------
# Score detail insert
# ---------------------------------------------------------------------------

SCORE_INSERT_SQL = (
    "INSERT INTO attempt_score_detail ("
    " detail_id, attempt_id, word_accuracy, phoneme_accuracy, pa_available, fluency_score,"
    " disfluency_rate, pause_score, speech_rate_wpm, speech_rate_score, confidence_score,"
    " rl_score, tc_score, aq_score, behavioral_score, dominant_emotion, emotion_score,"
    " engagement_score, speech_score, final_score, adaptive_decision, pass_fail,"
    " fail_reason, performance_level, low_confidence_flag, review_recommended, asr_transcript, audio_duration_sec,"
    " target_phoneme_results, created_at"
    ") VALUES ("
    " %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW()"
    ")"
)


def insert_score_detail(cur, params: tuple) -> None:
    cur.execute(SCORE_INSERT_SQL, params)


# ---------------------------------------------------------------------------
# Patient task progress
# ---------------------------------------------------------------------------

def upsert_patient_task_progress(
    cur,
    patient_id: str,
    task_id: str,
    current_level_id: str | None,
    adaptive_decision: str,
    final_score: float,
    pass_fail: str,
) -> None:
    if not task_id:
        return

    cur.execute(
        "SELECT level_id FROM task_level WHERE task_id = %s ORDER BY difficulty_score ASC",
        (task_id,),
    )
    ordered_levels = [r[0] for r in cur.fetchall()]
    if not ordered_levels:
        return

    cur.execute(
        "SELECT progress_id, current_level_id, consecutive_passes, consecutive_fails,"
        " overall_accuracy, total_attempts, sessions_at_level"
        " FROM patient_task_progress"
        " WHERE patient_id = %s AND task_id = %s",
        (patient_id, task_id),
    )
    prog = cur.fetchone()
    is_pass = pass_fail == "pass"
    new_level_id = current_level_id or (ordered_levels[0] if ordered_levels else None)

    if prog:
        _update_existing_progress(
            cur, prog, ordered_levels, is_pass, new_level_id,
            adaptive_decision, final_score,
        )
    else:
        _insert_new_progress(
            cur, patient_id, task_id, new_level_id,
            is_pass, final_score,
        )


def _update_existing_progress(cur, prog, ordered_levels, is_pass, new_level_id, adaptive_decision, final_score):
    progress_id, cur_level, cons_pass, cons_fail, overall_acc, total_att, sessions_at_level = prog
    new_cons_pass = (cons_pass or 0) + 1 if is_pass else 0
    new_cons_fail = (cons_fail or 0) + 1 if not is_pass else 0
    new_total = (total_att or 0) + 1
    prev_acc = float(overall_acc) if overall_acc is not None else final_score
    new_acc = round(((prev_acc * (total_att or 0)) + final_score) / new_total, 2)

    effective_level = cur_level or new_level_id
    try:
        idx = ordered_levels.index(effective_level)
    except ValueError:
        idx = 0

    if adaptive_decision == "advance":
        idx = min(idx + 1, len(ordered_levels) - 1)
    elif adaptive_decision == "drop":
        idx = max(idx - 1, 0)

    previous_level_id = effective_level
    resolved_level_id = ordered_levels[idx]
    new_sessions = 1 if resolved_level_id != previous_level_id else int(sessions_at_level or 0) + 1

    cur.execute(
        "UPDATE patient_task_progress"
        " SET current_level_id=%s, consecutive_passes=%s, consecutive_fails=%s,"
        " overall_accuracy=%s, last_final_score=%s, total_attempts=%s,"
        " sessions_at_level=%s, last_attempted_at=NOW()"
        " WHERE progress_id=%s",
        (resolved_level_id, new_cons_pass, new_cons_fail, new_acc,
         round(final_score, 2), new_total, new_sessions, progress_id),
    )


def _insert_new_progress(cur, patient_id, task_id, new_level_id, is_pass, final_score):
    cur.execute(
        "INSERT INTO patient_task_progress"
        " (progress_id, patient_id, task_id, current_level_id, consecutive_passes, consecutive_fails,"
        " overall_accuracy, last_final_score, total_attempts, sessions_at_level, last_attempted_at)"
        " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1,%s,NOW())",
        (str(uuid.uuid4()), patient_id, task_id, new_level_id,
         1 if is_pass else 0, 0 if is_pass else 1,
         round(final_score, 2), round(final_score, 2), 1),
    )


# ---------------------------------------------------------------------------
# Session emotion summary
# ---------------------------------------------------------------------------

def upsert_session_emotion_summary(cur, session_id: str, patient_id: str) -> None:
    cur.execute(
        "SELECT asd.dominant_emotion, asd.engagement_score, asd.pass_fail"
        " FROM attempt_score_detail asd"
        " JOIN session_prompt_attempt spa ON spa.attempt_id = asd.attempt_id"
        " WHERE spa.session_id = %s",
        (session_id,),
    )
    rows = cur.fetchall()
    if not rows:
        return

    emotions = [r[0] for r in rows if r[0]]
    engagement_scores = [float(r[1]) for r in rows if r[1] is not None]
    drop_count = sum(1 for r in rows if r[2] == "fail")

    dominant = Counter(emotions).most_common(1)[0][0] if emotions else "neutral"
    avg_engagement = round(sum(engagement_scores) / len(engagement_scores), 2) if engagement_scores else 0.0
    frustration_scores = [float(r[1]) for r in rows if r[0] in ("angry", "fearful") and r[1] is not None]
    avg_frustration = round(sum(frustration_scores) / len(frustration_scores), 2) if frustration_scores else 0.0

    cur.execute(
        "SELECT summary_id FROM session_emotion_summary WHERE session_id = %s",
        (session_id,),
    )
    existing = cur.fetchone()
    if existing:
        cur.execute(
            "UPDATE session_emotion_summary"
            " SET dominant_emotion=%s, avg_frustration=%s, avg_engagement=%s, drop_count=%s"
            " WHERE session_id=%s",
            (dominant, avg_frustration, avg_engagement, drop_count, session_id),
        )
    else:
        cur.execute(
            "INSERT INTO session_emotion_summary"
            " (summary_id, session_id, patient_id, session_date, dominant_emotion,"
            " avg_frustration, avg_engagement, drop_count)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (str(uuid.uuid4()), session_id, patient_id, date.today().isoformat(),
             dominant, avg_frustration, avg_engagement, drop_count),
        )


# ---------------------------------------------------------------------------
# Review notification
# ---------------------------------------------------------------------------

def create_review_notification(cur, therapist_id: str, patient_id: str, attempt_id: str) -> None:
    cur.execute(
        "INSERT INTO therapist_notification"
        " (notification_id, therapist_id, type, patient_id, attempt_id, message, is_read, created_at)"
        " VALUES (%s,%s,%s,%s,%s,%s,false,NOW())",
        (
            str(uuid.uuid4()),
            therapist_id,
            "review_flagged",
            patient_id,
            attempt_id,
            "An attempt has been flagged for review due to low ASR confidence.",
        ),
    )


# ---------------------------------------------------------------------------
# WebSocket payload builder + publisher
# ---------------------------------------------------------------------------

def build_ws_payload(
    attempt_id: str,
    attempt_number: int,
    transcript: str,
    word_accuracy: float,
    phoneme_accuracy: float | None,
    pa_available: bool,
    fluency_score: float,
    speech_rate_wpm: int,
    speech_rate_score: float,
    confidence_score: float,
    speech_score: float,
    behavioral_score: float,
    engagement_score: float,
    emotion_score: float,
    final_score: float,
    pass_fail: str,
    adaptive_decision: str,
    performance_level: str,
    dominant_emotion: str,
    review_recommended: bool,
    fail_reason: str | None,
) -> dict:
    return {
        "type": "score_ready",
        "attempt_id": attempt_id,
        "attempt_number": attempt_number,
        "final_score": final_score,
        "pass_fail": pass_fail,
        "adaptive_decision": adaptive_decision,
        "performance_level": performance_level,
        "dominant_emotion": dominant_emotion,
        "speech_score": speech_score,
        "behavioral_score": behavioral_score,
        "engagement_score": engagement_score,
        "emotion_score": emotion_score,
        "word_accuracy": word_accuracy,
        "phoneme_accuracy": phoneme_accuracy,
        "pa_available": pa_available,
        "fluency_score": fluency_score,
        "speech_rate_wpm": speech_rate_wpm,
        "speech_rate_score": speech_rate_score,
        "confidence_score": confidence_score,
        "asr_transcript": transcript,
        "review_recommended": review_recommended,
        "fail_reason": fail_reason,
    }


def publish_score_event(patient_id: str, payload: dict) -> None:
    redis_client = redis.from_url(settings.redis_url)
    redis_client.publish(f"ws:patient:{patient_id}", json.dumps(payload))
