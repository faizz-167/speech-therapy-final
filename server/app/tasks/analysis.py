import uuid
import os
import json
from datetime import datetime
from numbers import Number
import psycopg2
import redis

from app.celery_app import celery_app
from app.config import settings
from app.scoring.engine import score_attempt, weights_from_db_row, ScoringWeights
from app.utils.session_notes import parse_session_notes, serialize_session_notes
from app.tasks.plan_regeneration import regenerate_plan_after_escalation


def _get_conn():
    return psycopg2.connect(settings.database_url_sync)


def _compute_word_accuracy(transcript, target_text):
    if not target_text or not transcript:
        return 0.0
    target_words = {
        word.strip(".,!?;:\"'()[]{}").lower()
        for word in target_text.split()
        if word.strip(".,!?;:\"'()[]{}")
    }
    spoken_words = {
        word.strip(".,!?;:\"'()[]{}").lower()
        for word in transcript.split()
        if word.strip(".,!?;:\"'()[]{}")
    }
    if not target_words:
        return 0.0
    matches = target_words & spoken_words
    return round((len(matches) / len(target_words)) * 100, 2)


def _compute_speech_rate_wpm(transcript: str, duration: float, words: list[dict] | None = None) -> float:
    word_count = len(transcript.split())
    if word_count == 0:
        return 0.0

    timed_words = [
        word
        for word in (words or [])
        if word.get("start") is not None and word.get("end") is not None
    ]
    if len(timed_words) >= 2:
        speech_span = float(timed_words[-1]["end"]) - float(timed_words[0]["start"])
    elif len(timed_words) == 1:
        speech_span = float(timed_words[0]["end"]) - float(timed_words[0]["start"])
    else:
        speech_span = duration

    speech_span = max(0.5, speech_span)
    return (word_count / speech_span) * 60


def _compute_speech_rate_score(wpm, ideal_min=80, ideal_max=120, tolerance=20):
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


def _compute_rl_score(mic_at, speech_at):
    if not mic_at or not speech_at:
        return 70.0
    try:
        t_mic = datetime.fromisoformat(mic_at)
        t_speech = datetime.fromisoformat(speech_at)
        latency = (t_speech - t_mic).total_seconds()
        if latency <= 1.0:
            return 100.0
        elif latency <= 3.0:
            return 80.0
        elif latency <= 5.0:
            return 60.0
        return 40.0
    except Exception:
        return 70.0


def _compute_tc_score(transcript, target_word_count, target_duration, duration):
    if target_word_count:
        spoken = len(transcript.split())
        ratio = min(spoken / target_word_count, 1.0)
        return round(ratio * 100, 2)
    if target_duration and duration > 0:
        ratio = min(duration / target_duration, 1.0)
        return round(ratio * 100, 2)
    return 80.0


def _compute_aq_score(transcript):
    words = transcript.strip().split()
    if len(words) < 2:
        return 30.0
    elif len(words) < 5:
        return 60.0
    return 85.0


def _needs_asr_review(transcript: str, target_text: str | None, avg_confidence: float, word_accuracy: float) -> bool:
    if avg_confidence < 0.55:
        return True
    if not transcript.strip():
        return True
    if target_text and word_accuracy == 0.0 and len(transcript.split()) >= 3:
        return True
    return False


def _to_builtin(value):
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, Number):
        return value
    return value


def _as_float(value, default: float = 0.0) -> float:
    value = _to_builtin(value)
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value, default: int = 0) -> int:
    value = _to_builtin(value)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_target_phonemes(value) -> list[str]:
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


CLINICAL_EMOTION_BASE_SCORES = {
    "child": {
        "happy": 95.0,
        "neutral": 80.0,
        "sad": 50.0,
        "angry": 35.0,
    },
    "adult": {
        "happy": 85.0,
        "neutral": 90.0,
        "sad": 50.0,
        "angry": 35.0,
    },
    "senior": {
        "happy": 85.0,
        "neutral": 90.0,
        "sad": 50.0,
        "angry": 35.0,
    },
}


def _score_clinical_emotion(emotion_result: dict, age_group: str) -> float | None:
    dominant_emotion = str(emotion_result.get("dominant_emotion") or "").lower()
    age_scores = CLINICAL_EMOTION_BASE_SCORES.get(age_group) or CLINICAL_EMOTION_BASE_SCORES["adult"]
    if dominant_emotion not in age_scores:
        return None

    raw_emotion_score = _as_float(emotion_result.get("emotion_score"))
    confidence = _as_float(emotion_result.get("confidence"), default=raw_emotion_score / 100.0)
    confidence = min(1.0, max(0.0, confidence))
    return round(min(100.0, max(0.0, age_scores[dominant_emotion] * confidence)), 2)


def _build_emotion_weight_map(row) -> dict[str, float]:
    if not row:
        return {}
    return {
        "happy": _as_float(row[0]),
        "excited": _as_float(row[1]),
        "neutral": _as_float(row[2]),
        "surprised": _as_float(row[3]),
        "sad": _as_float(row[4]),
        "angry": _as_float(row[5]),
        "fearful": _as_float(row[6]),
        "positive_affect": _as_float(row[7]),
        "focused": _as_float(row[8]),
    }


def _score_emotion_with_config(emotion_result: dict, emotion_weights_row, age_group: str = "adult") -> float:
    raw_emotion_score = _as_float(emotion_result.get("emotion_score"))
    dominant_emotion = emotion_result.get("dominant_emotion")
    clinical_score = _score_clinical_emotion(emotion_result, age_group)
    if clinical_score is not None:
        return clinical_score

    if not dominant_emotion or emotion_weights_row is None:
        return raw_emotion_score

    weights = _build_emotion_weight_map(emotion_weights_row)
    if not weights:
        return raw_emotion_score

    confidence = _as_float(emotion_result.get("confidence"), default=raw_emotion_score / 100.0)

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


_SCORE_INSERT_SQL = (
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


def _exec_insert_score_detail(cur, params: tuple) -> None:
    cur.execute(_SCORE_INSERT_SQL, params)


def _build_ws_payload(
    attempt_id: str,
    attempt_number: int,
    transcript: str,
    wa: float, pa: float | None, pa_available: bool, fs: float,
    wpm: int, srs: float, cs: float,
    speech_score: float, behavioral_score: float, engagement_score: float,
    emotion_score: float, final_score: float, pass_fail: str, adaptive_decision: str,
    performance_level: str, dominant_emotion: str,
    review_recommended: bool, fail_reason: str | None,
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
        "word_accuracy": wa,
        "phoneme_accuracy": pa,
        "pa_available": pa_available,
        "fluency_score": fs,
        "speech_rate_wpm": wpm,
        "speech_rate_score": srs,
        "confidence_score": cs,
        "asr_transcript": transcript,
        "review_recommended": review_recommended,
        "fail_reason": fail_reason,
    }


def _is_no_speech(transcript: str, duration: float, avg_confidence: float) -> bool:
    normalized = transcript.strip()
    if not normalized:
        return True
    word_count = len(normalized.split())
    if word_count == 0:
        return True
    # Treat extremely short, low-confidence output as silence/background noise.
    return word_count <= 1 and duration < 1.0 and avg_confidence < 0.35


def _upsert_patient_task_progress(
    cur,
    patient_id: str,
    task_id: str,
    current_level_id: str | None,
    adaptive_decision: str,
    final_score: float,
    pass_fail: str,
) -> None:
    """Upsert patient_task_progress for adaptive difficulty tracking."""
    if not task_id:
        return

    # Load all levels for this task ordered by difficulty ascending
    cur.execute(
        "SELECT level_id FROM task_level WHERE task_id = %s ORDER BY difficulty_score ASC",
        (task_id,),
    )
    level_rows = cur.fetchall()
    ordered_levels = [r[0] for r in level_rows]
    if not ordered_levels:
        return

    # Get or create the progress row
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
        new_level_id = ordered_levels[idx]
        new_sessions_at_level = 1 if new_level_id != previous_level_id else int(sessions_at_level or 0) + 1

        cur.execute(
            "UPDATE patient_task_progress"
            " SET current_level_id=%s, consecutive_passes=%s, consecutive_fails=%s,"
            " overall_accuracy=%s, last_final_score=%s, total_attempts=%s,"
            " sessions_at_level=%s, last_attempted_at=NOW()"
            " WHERE progress_id=%s",
            (
                new_level_id,
                new_cons_pass,
                new_cons_fail,
                new_acc,
                round(final_score, 2),
                new_total,
                new_sessions_at_level,
                progress_id,
            ),
        )
    else:
        import uuid as _uuid
        new_progress_id = str(_uuid.uuid4())
        new_cons_pass = 1 if is_pass else 0
        new_cons_fail = 0 if is_pass else 1
        cur.execute(
            "INSERT INTO patient_task_progress"
            " (progress_id, patient_id, task_id, current_level_id, consecutive_passes, consecutive_fails,"
            " overall_accuracy, last_final_score, total_attempts, sessions_at_level, last_attempted_at)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1,%s,NOW())",
            (new_progress_id, patient_id, task_id, new_level_id,
             new_cons_pass, new_cons_fail, round(final_score, 2), round(final_score, 2), 1),
        )


def _upsert_session_emotion_summary(cur, session_id: str, patient_id: str) -> None:
    """Recalculate and upsert session_emotion_summary from all scored attempts in session."""
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

    from collections import Counter
    dominant = Counter(emotions).most_common(1)[0][0] if emotions else "neutral"
    avg_eng = round(sum(engagement_scores) / len(engagement_scores), 2) if engagement_scores else 0.0
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
            (dominant, avg_frustration, avg_eng, drop_count, session_id),
        )
    else:
        import uuid as _uuid
        from datetime import date as _date
        cur.execute(
            "INSERT INTO session_emotion_summary"
            " (summary_id, session_id, patient_id, session_date, dominant_emotion,"
            " avg_frustration, avg_engagement, drop_count)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (str(_uuid.uuid4()), session_id, patient_id, _date.today().isoformat(),
             dominant, avg_frustration, avg_eng, drop_count),
        )


def _create_review_notification(cur, therapist_id: str, patient_id: str, attempt_id: str) -> None:
    """Create a therapist_notification row when an attempt needs manual review."""
    import uuid as _uuid
    cur.execute(
        "INSERT INTO therapist_notification"
        " (notification_id, therapist_id, type, patient_id, attempt_id, message, is_read, created_at)"
        " VALUES (%s,%s,%s,%s,%s,%s,false,NOW())",
        (
            str(_uuid.uuid4()),
            therapist_id,
            "review_flagged",
            patient_id,
            attempt_id,
            "An attempt has been flagged for review due to low ASR confidence.",
        ),
    )


def _read_session_notes(cur, session_id: str) -> dict:
    cur.execute(
        "SELECT session_notes FROM session WHERE session_id = %s",
        (session_id,),
    )
    row = cur.fetchone()
    raw = row[0] if row else None
    return parse_session_notes(raw)


def _write_session_notes(cur, session_id: str, notes: dict) -> None:
    cur.execute(
        "UPDATE session SET session_notes = %s WHERE session_id = %s",
        (serialize_session_notes(notes), session_id),
    )


def _get_task_name(cur, task_id: str) -> str:
    cur.execute("SELECT name FROM task WHERE task_id = %s", (task_id,))
    row = cur.fetchone()
    return row[0] if row else "Unknown Task"


def _mark_prompt_terminal(
    cur,
    session_id: str,
    prompt_id: str,
    pass_fail: str,
    attempt_number: int,
) -> None:
    if pass_fail != "pass" and attempt_number < 3:
        return

    cur.execute(
        "SELECT session_notes FROM session WHERE session_id = %s",
        (session_id,),
    )
    row = cur.fetchone()
    session_notes = {}
    if row and row[0]:
        try:
            session_notes = json.loads(row[0])
        except (TypeError, ValueError):
            session_notes = {}

    completed_prompt_ids = list(session_notes.get("completed_prompt_ids") or [])
    passed_prompt_ids = list(session_notes.get("passed_prompt_ids") or [])

    if prompt_id not in completed_prompt_ids:
        completed_prompt_ids.append(prompt_id)
    if pass_fail == "pass" and prompt_id not in passed_prompt_ids:
        passed_prompt_ids.append(prompt_id)

    session_notes["completed_prompt_ids"] = completed_prompt_ids
    session_notes["passed_prompt_ids"] = passed_prompt_ids
    cur.execute(
        "UPDATE session SET session_notes = %s WHERE session_id = %s",
        (json.dumps(session_notes), session_id),
    )


@celery_app.task(name="app.tasks.analysis.analyze_attempt", bind=True, max_retries=2)
def analyze_attempt(self, attempt_id):
    conn = None
    try:
        # Lazy ML imports — only loaded when the worker actually runs the task
        from app.ml.whisper_asr import transcribe
        from app.ml.hubert_phoneme import align_phonemes
        from app.ml.spacy_disfluency import score_disfluency
        from app.ml.speechbrain_emotion import classify_emotion

        conn = _get_conn()
        cur = conn.cursor()

        cur.execute(
            "SELECT spa.attempt_id, spa.attempt_number, spa.session_id, spa.prompt_id, spa.audio_file_path,"
            " spa.mic_activated_at, spa.speech_start_at, spa.task_mode, spa.prompt_type,"
            " p.display_content, p.target_response, p.level_id, p.target_phonemes,"
            " p.target_word_count, p.target_duration_sec, p.aq_relevance_threshold,"
            " p.speech_target,"
            " tl.task_id,"
            " s.patient_id, s.plan_id"
            " FROM session_prompt_attempt spa"
            " JOIN session s ON s.session_id = spa.session_id"
            " JOIN prompt p ON p.prompt_id = spa.prompt_id"
            " LEFT JOIN task_level tl ON tl.level_id = p.level_id"
            " WHERE spa.attempt_id = %s",
            (attempt_id,),
        )
        row = cur.fetchone()
        if not row:
            return

        (
            attempt_id_db, attempt_number, session_id, prompt_id, audio_path,
            mic_at, speech_at, task_mode, prompt_type,
            display_content, target_response, level_id, prompt_target_phonemes,
            target_word_count, target_duration_sec, aq_threshold,
            speech_target, task_id, patient_id, plan_id,
        ) = row

        if not audio_path or not os.path.exists(audio_path):
            cur.execute("UPDATE session_prompt_attempt SET result='fail' WHERE attempt_id=%s", (attempt_id,))
            conn.commit()
            return

        weights = ScoringWeights()
        if task_id:
            cur.execute("SELECT * FROM task_scoring_weights WHERE task_id=%s", (task_id,))
            wrow = cur.fetchone()
            if wrow:
                col_names = [desc[0] for desc in cur.description]
                wdict = dict(zip(col_names, wrow))

                class WeightRow:
                    pass

                w = WeightRow()
                for k, v in wdict.items():
                    setattr(w, k, v)
                weights = weights_from_db_row(w)

        ideal_wpm_min, ideal_wpm_max, wpm_tolerance = 80, 120, 20
        if task_id:
            cur.execute(
                "SELECT ideal_wpm_min, ideal_wpm_max, wpm_tolerance FROM task WHERE task_id=%s",
                (task_id,),
            )
            trow = cur.fetchone()
            if trow and all(v is not None for v in trow):
                ideal_wpm_min, ideal_wpm_max, wpm_tolerance = trow

        # Load patient defect IDs for per-defect PA threshold lookup
        cur.execute(
            "SELECT pre_assigned_defect_ids, date_of_birth FROM patient WHERE patient_id = %s",
            (patient_id,),
        )
        patient_row = cur.fetchone()
        patient_defect_ids: list[str] = []
        patient_dob = None
        if patient_row:
            defect_json, patient_dob = patient_row
            if defect_json and isinstance(defect_json, dict):
                patient_defect_ids = defect_json.get("defect_ids", [])

        cur.execute(
            "SELECT assigned_therapist_id FROM patient WHERE patient_id = %s",
            (patient_id,),
        )
        therapist_row = cur.fetchone()
        assigned_therapist_id = str(therapist_row[0]) if therapist_row and therapist_row[0] else None

        # Per-defect PA thresholds — pick the strictest (lowest) min_pa_to_pass
        defect_pa_min: float | None = None
        if patient_defect_ids:
            cur.execute(
                "SELECT min_pa_to_pass FROM defect_pa_threshold WHERE defect_id = ANY(%s)",
                (patient_defect_ids,),
            )
            pa_rows = cur.fetchall()
            if pa_rows:
                defect_pa_min = min(float(r[0]) for r in pa_rows)

        # Emotion weights config by age group
        age_group = "child"
        if patient_dob:
            from datetime import date as _date
            try:
                if hasattr(patient_dob, "year"):
                    dob = patient_dob
                else:
                    dob = _date.fromisoformat(str(patient_dob))
                today = _date.today()
                age_years = (today - dob).days // 365
                age_group = "child" if age_years < 18 else ("senior" if age_years >= 65 else "adult")
            except Exception:
                age_group = "adult"

        cur.execute(
            "SELECT w_happy, w_excited, w_neutral, w_surprised, w_sad, w_angry, w_fearful,"
            " w_positive_affect, w_focused"
            " FROM emotion_weights_config WHERE age_group = %s",
            (age_group,),
        )
        emotion_weights_row = cur.fetchone()

        # Prompt-level adaptive threshold override
        cur.execute(
            "SELECT advance_to_next_level FROM adaptive_threshold WHERE prompt_id = %s",
            (prompt_id,),
        )
        prompt_advance_override = cur.fetchone()
        prompt_advance_threshold: float | None = None
        if prompt_advance_override and prompt_advance_override[0] is not None:
            prompt_advance_threshold = float(prompt_advance_override[0])

        conn.close()
        conn = None

        # Retry guard: if this session is already marked escalated (committed by a prior
        # successful run), skip all ML and mutations and just republish the WS event.
        # Without this, a Celery retry re-inserts score_detail and re-updates progress
        # before reaching the later notes["escalated"] check.
        if attempt_number >= 3:
            _rg_conn = _get_conn()
            _rg_cur = _rg_conn.cursor()
            _rg_notes = _read_session_notes(_rg_cur, str(session_id))
            _rg_conn.close()
            if _rg_notes.get("escalated"):
                r = redis.from_url(settings.redis_url)
                r.publish(
                    f"ws:patient:{patient_id}",
                    json.dumps({
                        "type": "score_ready",
                        "attempt_id": attempt_id,
                        "attempt_number": attempt_number,
                        "adaptive_decision": "escalated",
                        "pass_fail": "fail",
                        "final_score": 0.0,
                        "performance_level": "needs_improvement",
                        "dominant_emotion": "neutral",
                        "speech_score": 0.0,
                        "behavioral_score": 0.0,
                        "engagement_score": 0.0,
                        "word_accuracy": 0.0,
                        "phoneme_accuracy": None,
                        "pa_available": False,
                        "fluency_score": 0.0,
                        "speech_rate_wpm": 0,
                        "speech_rate_score": 0.0,
                        "confidence_score": 0.0,
                        "asr_transcript": "",
                        "review_recommended": False,
                        "fail_reason": None,
                    }),
                )
                return

        target_text = target_response
        if not target_text and speech_target and isinstance(speech_target, dict):
            target_text = speech_target.get("text")

        asr = transcribe(audio_path, expected_text=target_text)
        transcript = asr["transcript"]
        duration = _as_float(asr["duration"])
        avg_confidence = _as_float(asr["avg_confidence"])

        if _is_no_speech(transcript, duration, avg_confidence):
            conn = _get_conn()
            cur = conn.cursor()
            adaptive_decision = "drop" if attempt_number >= 3 else "stay"
            _exec_insert_score_detail(
                cur,
                (
                    str(uuid.uuid4()), attempt_id, 0.0, None, False, 0.0,
                    0.0, 0.0, 0, 0.0, 0.0,
                    0.0, 0.0, 0.0, 0.0, "neutral", 0.0,
                    0.0, 0.0, 0.0, adaptive_decision, "fail",
                    "No speech detected", "needs_improvement", True, True, transcript, duration,
                    "{}",
                ),
            )
            cur.execute(
                "UPDATE session_prompt_attempt SET result=%s, asr_transcript=%s, speech_detected=false"
                " WHERE attempt_id=%s",
                ("fail", transcript, attempt_id),
            )
            _upsert_patient_task_progress(
                cur, str(patient_id), task_id,
                level_id, adaptive_decision, 0.0, "fail",
            )
            _mark_prompt_terminal(cur, str(session_id), prompt_id, "fail", attempt_number)
            _ns_notes = _read_session_notes(cur, str(session_id))
            if str(prompt_id) not in _ns_notes["attempted_prompt_ids"]:
                _ns_notes["attempted_prompt_ids"].append(str(prompt_id))
            _write_session_notes(cur, str(session_id), _ns_notes)

            # Adaptive intervention block for no-speech attempt 3.
            # Mirrors the normal-scoring adaptive block; the initial "drop" in
            # _upsert_patient_task_progress above is already applied, so the
            # non-beginner branch here only increments interventions (no second upsert).
            if attempt_number >= 3:
                _ns_task_name = _get_task_name(cur, str(task_id)) if task_id else "Unknown Task"
                cur.execute("SELECT level_name FROM task_level WHERE level_id = %s", (level_id,))
                _ns_lvl_row = cur.fetchone()
                _ns_level_name = _ns_lvl_row[0] if _ns_lvl_row else None

                if _ns_notes.get("escalated"):
                    adaptive_decision = "escalated"
                elif _ns_notes["adaptive_interventions"] >= 2:
                    _ns_notes["escalated"] = True
                    _ns_notes["escalation_level"] = _ns_level_name
                    _write_session_notes(cur, str(session_id), _ns_notes)
                    adaptive_decision = "escalated"
                    if assigned_therapist_id:
                        cur.execute(
                            "INSERT INTO therapist_notification"
                            " (notification_id, therapist_id, type, patient_id, attempt_id, message, is_read, created_at)"
                            " VALUES (%s, %s, %s, %s, %s, %s, false, NOW())",
                            (
                                str(uuid.uuid4()),
                                assigned_therapist_id,
                                "task_escalated",
                                str(patient_id),
                                str(attempt_id),
                                f"Task '{_ns_task_name}' escalated after 2 failed interventions"
                                f" (no speech detected). New plan will be generated at a lower level.",
                            ),
                        )
                        regenerate_plan_after_escalation.delay(
                            str(patient_id), str(assigned_therapist_id), _ns_level_name or "beginner"
                        )
                else:
                    _ns_force_escalate = False
                    if _ns_level_name == "beginner":
                        cur.execute(
                            "SELECT p.prompt_id FROM prompt p"
                            " JOIN task_level tl ON tl.level_id = p.level_id"
                            " WHERE tl.task_id = %s AND tl.level_name = 'beginner'",
                            (str(task_id),),
                        )
                        _ns_all_beginner_ids = [str(r[0]) for r in cur.fetchall()]
                        _ns_candidates = [pid for pid in _ns_all_beginner_ids
                                          if pid not in _ns_notes["attempted_prompt_ids"]]
                        if _ns_candidates:
                            adaptive_decision = "alternate_prompt"
                        else:
                            _ns_force_escalate = True
                    # Non-beginner: drop already applied above; just track the intervention.

                    if _ns_force_escalate:
                        _ns_notes["adaptive_interventions"] = 2
                        _ns_notes["escalated"] = True
                        _ns_notes["escalation_level"] = _ns_level_name
                        _write_session_notes(cur, str(session_id), _ns_notes)
                        adaptive_decision = "escalated"
                        if assigned_therapist_id:
                            cur.execute(
                                "INSERT INTO therapist_notification"
                                " (notification_id, therapist_id, type, patient_id, attempt_id, message, is_read, created_at)"
                                " VALUES (%s, %s, %s, %s, %s, %s, false, NOW())",
                                (
                                    str(uuid.uuid4()),
                                    assigned_therapist_id,
                                    "task_escalated",
                                    str(patient_id),
                                    str(attempt_id),
                                    f"Task '{_ns_task_name}' escalated — no beginner candidates remain"
                                    f" (no speech detected). New plan will be generated.",
                                ),
                            )
                            regenerate_plan_after_escalation.delay(
                                str(patient_id), str(assigned_therapist_id), _ns_level_name or "beginner"
                            )
                    else:
                        _ns_notes["adaptive_interventions"] += 1
                        _write_session_notes(cur, str(session_id), _ns_notes)
                        if assigned_therapist_id:
                            cur.execute(
                                "INSERT INTO therapist_notification"
                                " (notification_id, therapist_id, type, patient_id, attempt_id, message, is_read, created_at)"
                                " VALUES (%s, %s, %s, %s, %s, %s, false, NOW())",
                                (
                                    str(uuid.uuid4()),
                                    assigned_therapist_id,
                                    "task_attempt_failed",
                                    str(patient_id),
                                    str(attempt_id),
                                    f"Patient failed '{_ns_task_name}' (no speech, attempt 3)."
                                    f" Adaptive intervention {_ns_notes['adaptive_interventions']} of 2: {adaptive_decision}.",
                                ),
                            )

            _upsert_session_emotion_summary(cur, str(session_id), str(patient_id))
            if assigned_therapist_id:
                _create_review_notification(cur, assigned_therapist_id, str(patient_id), str(attempt_id))
            conn.commit()
            r = redis.from_url(settings.redis_url)
            r.publish(
                f"ws:patient:{patient_id}",
                json.dumps(_build_ws_payload(
                    attempt_id, attempt_number, transcript,
                    0.0, None, False, 0.0, 0, 0.0, 0.0,
                    0.0, 0.0, 0.0, 0.0,
                    0.0, "fail", adaptive_decision, "needs_improvement", "neutral",
                    True, "No speech detected",
                )),
            )
            return

        target_phonemes = _parse_target_phonemes(prompt_target_phonemes)
        words = asr.get("words") or []

        phoneme_result = align_phonemes(
            audio_path,
            transcript,
            target_phonemes=target_phonemes,
            reference_text=target_text,
        )
        disfluency_result = score_disfluency(transcript, duration, words)
        emotion_result = classify_emotion(audio_path)

        wpm = _as_float(_compute_speech_rate_wpm(transcript, duration, words))
        wa_available = bool(target_text)
        if wa_available:
            wa = _as_float(_compute_word_accuracy(transcript, target_text), default=0.0)
        else:
            wa = 0.0
        pa_available = bool(phoneme_result.get("inference_ok"))
        pa = _as_float(phoneme_result.get("phoneme_accuracy"), default=0.0) if pa_available else None
        fs = _as_float(disfluency_result["fluency_score"], default=50.0)
        srs = _as_float(_compute_speech_rate_score(wpm, ideal_wpm_min, ideal_wpm_max, wpm_tolerance))
        cs = _as_float(min(100.0, avg_confidence * 100))
        rl_score = _as_float(_compute_rl_score(str(mic_at) if mic_at else None, str(speech_at) if speech_at else None), default=70.0)
        tc_score = _as_float(_compute_tc_score(transcript, target_word_count, target_duration_sec, duration), default=80.0)
        aq_score = _as_float(_compute_aq_score(transcript), default=30.0)
        emotion_score = _score_emotion_with_config(emotion_result, emotion_weights_row, age_group)
        dominant_emotion = emotion_result.get("dominant_emotion")

        scores = score_attempt(
            pa=pa, wa=wa, fs=fs, srs=srs, cs=cs,
            rl_score=rl_score, tc_score=tc_score, aq_score=aq_score,
            emotion_score=emotion_score, pa_available=pa_available,
            wa_available=wa_available, weights=weights,
        )

        # Override PA cap threshold with defect-specific threshold if available
        if pa_available and defect_pa_min is not None and pa is not None and pa < defect_pa_min:
            final_score_override = min(scores["final_score"], weights.rule_severe_pa_score_cap)
            scores = {**scores, "final_score": round(final_score_override, 2)}
            scores["adaptive_decision"] = "drop"
            scores["pass_fail"] = "fail"
            scores["performance_level"] = "needs_improvement"

        # Apply prompt-level advance threshold override
        if prompt_advance_threshold is not None and scores["adaptive_decision"] == "advance":
            if scores["final_score"] < prompt_advance_threshold:
                scores = {**scores, "adaptive_decision": "stay", "pass_fail": "pass", "performance_level": "satisfactory"}

        if scores["pass_fail"] == "fail" and attempt_number < 3:
            scores = {**scores, "adaptive_decision": "stay"}

        behavioral_score = _as_float(scores["behavioral_score"])
        engagement_score = _as_float(scores["engagement_score"])
        speech_score = _as_float(scores["speech_score"])
        final_score = _as_float(scores["final_score"])
        adaptive_decision = scores["adaptive_decision"]
        pass_fail = scores["pass_fail"]
        performance_level = scores["performance_level"]
        low_confidence = avg_confidence < weights.rule_low_conf_threshold
        review_recommended = _needs_asr_review(transcript, target_text, avg_confidence, wa)
        fail_reason = None
        if review_recommended:
            fail_reason = "ASR transcript needs review"
        disfluency_rate = _as_float(disfluency_result["disfluency_rate"])
        pause_score = _as_float(disfluency_result["pause_score"])
        target_phoneme_results = json.dumps(phoneme_result.get("target_phoneme_results") or {})

        conn = _get_conn()
        cur = conn.cursor()
        wpm_int = _as_int(round(wpm))
        _exec_insert_score_detail(
            cur,
            (
                str(uuid.uuid4()), attempt_id, wa, pa, pa_available, fs,
                disfluency_rate, pause_score,
                wpm_int, srs, cs,
                rl_score, tc_score, aq_score, behavioral_score, dominant_emotion, emotion_score,
                engagement_score, speech_score, final_score, adaptive_decision, pass_fail,
                fail_reason, performance_level, low_confidence, review_recommended, transcript, duration,
                target_phoneme_results,
            ),
        )
        cur.execute(
            "UPDATE session_prompt_attempt SET result=%s, asr_transcript=%s, speech_detected=true"
            " WHERE attempt_id=%s",
            (pass_fail, transcript, attempt_id),
        )
        _upsert_patient_task_progress(
            cur, str(patient_id), task_id,
            level_id, adaptive_decision, final_score, pass_fail,
        )
        _mark_prompt_terminal(cur, str(session_id), prompt_id, pass_fail, attempt_number)

        # Subtask 3.5 — track attempted_prompt_ids on every scored attempt
        notes = _read_session_notes(cur, str(session_id))
        if str(prompt_id) not in notes["attempted_prompt_ids"]:
            notes["attempted_prompt_ids"].append(str(prompt_id))
        _write_session_notes(cur, str(session_id), notes)

        # Subtasks 3.6/3.7 — adaptive intervention block
        if attempt_number == 3 and pass_fail == "fail":
            task_name = _get_task_name(cur, str(task_id)) if task_id else "Unknown Task"
            cur.execute("SELECT level_name FROM task_level WHERE level_id = %s", (level_id,))
            _lvl_row = cur.fetchone()
            current_level_name = _lvl_row[0] if _lvl_row else None

            if notes["escalated"]:
                # Celery retry guard — escalation already committed, republish WS
                adaptive_decision = "escalated"
            elif notes["adaptive_interventions"] >= 2:
                # Force escalation
                notes["escalated"] = True
                notes["escalation_level"] = current_level_name
                _write_session_notes(cur, str(session_id), notes)
                if assigned_therapist_id:
                    cur.execute(
                        "INSERT INTO therapist_notification"
                        " (notification_id, therapist_id, type, patient_id, attempt_id, message, is_read, created_at)"
                        " VALUES (%s, %s, %s, %s, %s, %s, false, NOW())",
                        (
                            str(uuid.uuid4()),
                            assigned_therapist_id,
                            "task_escalated",
                            str(patient_id),
                            str(attempt_id),
                            f"Task '{task_name}' has been escalated after 2 failed interventions. "
                            f"Final score: {final_score:.1f}. New plan will be generated at a lower level.",
                        ),
                    )
                adaptive_decision = "escalated"
                if assigned_therapist_id:
                    regenerate_plan_after_escalation.delay(
                        str(patient_id), str(assigned_therapist_id), current_level_name or "beginner"
                    )
            else:
                force_escalate = False
                if current_level_name == "beginner":
                    cur.execute(
                        "SELECT p.prompt_id FROM prompt p"
                        " JOIN task_level tl ON tl.level_id = p.level_id"
                        " WHERE tl.task_id = %s AND tl.level_name = 'beginner'",
                        (str(task_id),),
                    )
                    all_beginner_ids = [str(r[0]) for r in cur.fetchall()]
                    candidates = [pid for pid in all_beginner_ids
                                  if pid not in notes["attempted_prompt_ids"]]
                    if candidates:
                        adaptive_decision = "alternate_prompt"
                    else:
                        force_escalate = True
                else:
                    # Drop already applied by the unconditional _upsert_patient_task_progress
                    # above (line ~749). A second call here would double-drop the level.
                    adaptive_decision = "drop"

                if force_escalate:
                    notes["adaptive_interventions"] = 2
                    notes["escalated"] = True
                    notes["escalation_level"] = current_level_name
                    _write_session_notes(cur, str(session_id), notes)
                    if assigned_therapist_id:
                        cur.execute(
                            "INSERT INTO therapist_notification"
                            " (notification_id, therapist_id, type, patient_id, attempt_id, message, is_read, created_at)"
                            " VALUES (%s, %s, %s, %s, %s, %s, false, NOW())",
                            (
                                str(uuid.uuid4()),
                                assigned_therapist_id,
                                "task_escalated",
                                str(patient_id),
                                str(attempt_id),
                                f"Task '{task_name}' has been escalated after 2 failed interventions. "
                                f"Final score: {final_score:.1f}. New plan will be generated at a lower level.",
                            ),
                        )
                    adaptive_decision = "escalated"
                    if assigned_therapist_id:
                        regenerate_plan_after_escalation.delay(
                            str(patient_id), str(assigned_therapist_id), current_level_name or "beginner"
                        )
                else:
                    notes["adaptive_interventions"] += 1
                    _write_session_notes(cur, str(session_id), notes)
                    if assigned_therapist_id:
                        cur.execute(
                            "INSERT INTO therapist_notification"
                            " (notification_id, therapist_id, type, patient_id, attempt_id, message, is_read, created_at)"
                            " VALUES (%s, %s, %s, %s, %s, %s, false, NOW())",
                            (
                                str(uuid.uuid4()),
                                assigned_therapist_id,
                                "task_attempt_failed",
                                str(patient_id),
                                str(attempt_id),
                                f"Patient failed '{task_name}' (attempt 3, score {final_score:.1f}). "
                                f"Adaptive intervention {notes['adaptive_interventions']} of 2 applied: {adaptive_decision}.",
                            ),
                        )

        _upsert_session_emotion_summary(cur, str(session_id), str(patient_id))
        if review_recommended and assigned_therapist_id:
            _create_review_notification(cur, assigned_therapist_id, str(patient_id), str(attempt_id))
        conn.commit()

        r = redis.from_url(settings.redis_url)
        r.publish(
            f"ws:patient:{patient_id}",
            json.dumps(_build_ws_payload(
                attempt_id, attempt_number, transcript,
                wa, pa, pa_available, fs, wpm_int, srs, cs,
                speech_score, behavioral_score, engagement_score,
                emotion_score, final_score, pass_fail, adaptive_decision, performance_level, dominant_emotion,
                review_recommended, fail_reason,
            )),
        )

    except RuntimeError as exc:
        try:
            if conn is None or conn.closed:
                conn = _get_conn()
            cur = conn.cursor()
            cur.execute(
                "UPDATE session_prompt_attempt SET result=%s, asr_transcript=%s WHERE attempt_id=%s",
                ("fail", str(exc), attempt_id),
            )
            conn.commit()
        finally:
            if conn is not None and not conn.closed:
                conn.close()
        raise
    except Exception as exc:
        try:
            if conn is not None and not conn.closed:
                conn.rollback()
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=5)
    finally:
        if conn is not None and not conn.closed:
            conn.close()
