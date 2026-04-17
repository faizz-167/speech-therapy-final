"""Celery task for speech attempt analysis.

Orchestrates ML inference → scoring → persistence → WebSocket publish.
All heavy logic is delegated to extracted modules:
  - scoring_helpers: pure computation (word accuracy, speech rate, emotion, etc.)
  - session_queue: adaptive queue management and escalation
  - attempt_persistence: DB writes and WebSocket publishing
"""

import json
import os
import types
import uuid
from datetime import date, datetime

import psycopg2
import redis

from app.celery_app import celery_app
from app.config import settings
from app.constants import MAX_ATTEMPTS_PER_PROMPT
from app.scoring.engine import ScoringWeights, score_attempt, weights_from_db_row
from app.tasks.attempt_persistence import (
    build_ws_payload,
    create_review_notification,
    insert_score_detail,
    publish_score_event,
    upsert_patient_task_progress,
    upsert_session_emotion_summary,
)
from app.tasks.plan_regeneration import regenerate_plan_after_escalation
from app.tasks.scoring_helpers import (
    apply_emotion_priority_override,
    as_float,
    as_int,
    compute_aq_score,
    compute_rl_score,
    compute_speech_rate_score,
    compute_speech_rate_wpm,
    compute_tc_score,
    compute_word_accuracy,
    is_no_speech,
    needs_asr_review,
    parse_target_phonemes,
    score_emotion_with_config,
)
from app.tasks.session_queue import (
    apply_session_queue_result,
    get_level_name_from_level_id,
    mark_prompt_terminal,
    read_session_notes,
)


def _get_conn():
    return psycopg2.connect(settings.database_url_sync)


# ---------------------------------------------------------------------------
# Context loading — all DB reads for a single attempt
# ---------------------------------------------------------------------------

def _load_attempt_context(cur, attempt_id: str) -> dict | None:
    """Load all data needed to score an attempt. Returns None if attempt not found."""
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
        return None

    (
        attempt_id_db, attempt_number, session_id, prompt_id, audio_path,
        mic_at, speech_at, task_mode, prompt_type,
        display_content, target_response, level_id, prompt_target_phonemes,
        target_word_count, target_duration_sec, aq_threshold,
        speech_target, task_id, patient_id, plan_id,
    ) = row

    return {
        "attempt_id": attempt_id_db,
        "attempt_number": attempt_number,
        "session_id": session_id,
        "prompt_id": prompt_id,
        "audio_path": audio_path,
        "mic_at": mic_at,
        "speech_at": speech_at,
        "task_mode": task_mode,
        "prompt_type": prompt_type,
        "target_response": target_response,
        "level_id": level_id,
        "prompt_target_phonemes": prompt_target_phonemes,
        "target_word_count": target_word_count,
        "target_duration_sec": target_duration_sec,
        "speech_target": speech_target,
        "task_id": task_id,
        "patient_id": patient_id,
        "plan_id": plan_id,
    }


def _load_scoring_config(cur, task_id, patient_id, prompt_id) -> dict:
    """Load weights, WPM targets, defect thresholds, emotion config, and age group."""
    weights = ScoringWeights()
    if task_id:
        cur.execute("SELECT * FROM task_scoring_weights WHERE task_id=%s", (task_id,))
        wrow = cur.fetchone()
        if wrow:
            col_names = [desc[0] for desc in cur.description]
            weight_namespace = types.SimpleNamespace(**dict(zip(col_names, wrow)))
            weights = weights_from_db_row(weight_namespace)

    ideal_wpm_min, ideal_wpm_max, wpm_tolerance = 80, 120, 20
    if task_id:
        cur.execute(
            "SELECT ideal_wpm_min, ideal_wpm_max, wpm_tolerance FROM task WHERE task_id=%s",
            (task_id,),
        )
        trow = cur.fetchone()
        if trow and all(v is not None for v in trow):
            ideal_wpm_min, ideal_wpm_max, wpm_tolerance = trow

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

    defect_pa_min: float | None = None
    if patient_defect_ids:
        cur.execute(
            "SELECT min_pa_to_pass FROM defect_pa_threshold WHERE defect_id = ANY(%s)",
            (patient_defect_ids,),
        )
        pa_rows = cur.fetchall()
        if pa_rows:
            defect_pa_min = min(float(r[0]) for r in pa_rows)

    age_group = _resolve_age_group(patient_dob)

    cur.execute(
        "SELECT w_happy, w_excited, w_neutral, w_surprised, w_sad, w_angry, w_fearful,"
        " w_positive_affect, w_focused"
        " FROM emotion_weights_config WHERE age_group = %s",
        (age_group,),
    )
    emotion_weights_row = cur.fetchone()

    prompt_advance_threshold: float | None = None
    cur.execute(
        "SELECT advance_to_next_level FROM adaptive_threshold WHERE prompt_id = %s",
        (prompt_id,),
    )
    prompt_advance_override = cur.fetchone()
    if prompt_advance_override and prompt_advance_override[0] is not None:
        prompt_advance_threshold = float(prompt_advance_override[0])

    return {
        "weights": weights,
        "ideal_wpm_min": ideal_wpm_min,
        "ideal_wpm_max": ideal_wpm_max,
        "wpm_tolerance": wpm_tolerance,
        "assigned_therapist_id": assigned_therapist_id,
        "defect_pa_min": defect_pa_min,
        "age_group": age_group,
        "emotion_weights_row": emotion_weights_row,
        "prompt_advance_threshold": prompt_advance_threshold,
    }


def _resolve_age_group(patient_dob) -> str:
    if not patient_dob:
        return "child"
    try:
        dob = patient_dob if hasattr(patient_dob, "year") else date.fromisoformat(str(patient_dob))
        age_years = (date.today() - dob).days // 365
        if age_years < 18:
            return "child"
        return "senior" if age_years >= 65 else "adult"
    except Exception:
        return "adult"


# ---------------------------------------------------------------------------
# ML pipeline
# ---------------------------------------------------------------------------

def _run_ml_pipeline(audio_path: str, target_text: str | None) -> dict:
    """Run all ML models and return raw results."""
    from app.ml.whisper_asr import transcribe
    from app.ml.hubert_phoneme import align_phonemes
    from app.ml.spacy_disfluency import score_disfluency
    from app.ml.speechbrain_emotion import classify_emotion

    asr = transcribe(audio_path, expected_text=target_text)
    transcript = asr["transcript"]
    target_phonemes = parse_target_phonemes(None)  # populated later from context

    phoneme_result = align_phonemes(
        audio_path, transcript,
        target_phonemes=[],
        reference_text=target_text,
    )
    disfluency_result = score_disfluency(transcript, as_float(asr["duration"]), asr.get("words") or [])
    emotion_result = classify_emotion(audio_path)

    return {
        "asr": asr,
        "transcript": transcript,
        "duration": as_float(asr["duration"]),
        "avg_confidence": as_float(asr["avg_confidence"]),
        "words": asr.get("words") or [],
        "phoneme_result": phoneme_result,
        "disfluency_result": disfluency_result,
        "emotion_result": emotion_result,
    }


# ---------------------------------------------------------------------------
# Score computation
# ---------------------------------------------------------------------------

def _compute_all_scores(ctx: dict, config: dict, ml: dict) -> dict:
    """Compute all metrics and return the final scores dict."""
    weights = config["weights"]
    transcript = ml["transcript"]
    duration = ml["duration"]
    avg_confidence = ml["avg_confidence"]
    words = ml["words"]
    target_text = ctx.get("target_response")
    if not target_text and ctx.get("speech_target") and isinstance(ctx["speech_target"], dict):
        target_text = ctx["speech_target"].get("text")

    wpm = as_float(compute_speech_rate_wpm(transcript, duration, words))
    word_accuracy_available = bool(target_text)
    word_accuracy = as_float(compute_word_accuracy(transcript, target_text), default=0.0) if word_accuracy_available else 0.0

    phoneme_result = ml["phoneme_result"]
    pa_available = bool(phoneme_result.get("inference_ok"))
    phoneme_accuracy = as_float(phoneme_result.get("phoneme_accuracy"), default=0.0) if pa_available else None

    fluency_score = as_float(ml["disfluency_result"]["fluency_score"], default=50.0)
    speech_rate_score = as_float(compute_speech_rate_score(
        wpm, config["ideal_wpm_min"], config["ideal_wpm_max"], config["wpm_tolerance"],
    ))
    confidence_score = as_float(min(100.0, avg_confidence * 100))
    rl_score = as_float(compute_rl_score(
        str(ctx["mic_at"]) if ctx["mic_at"] else None,
        str(ctx["speech_at"]) if ctx["speech_at"] else None,
    ), default=70.0)
    tc_score = as_float(compute_tc_score(
        transcript, ctx["target_word_count"], ctx["target_duration_sec"], duration,
    ), default=80.0)
    aq_score = as_float(compute_aq_score(transcript), default=30.0)
    emotion_score = score_emotion_with_config(
        ml["emotion_result"], config["emotion_weights_row"], config["age_group"],
    )
    dominant_emotion = ml["emotion_result"].get("dominant_emotion")

    scores = score_attempt(
        pa=phoneme_accuracy, wa=word_accuracy, fs=fluency_score,
        srs=speech_rate_score, cs=confidence_score,
        rl_score=rl_score, tc_score=tc_score, aq_score=aq_score,
        emotion_score=emotion_score, pa_available=pa_available,
        wa_available=word_accuracy_available, weights=weights,
    )
    scores = apply_emotion_priority_override(scores, dominant_emotion, emotion_score)

    # Defect-specific PA cap
    defect_pa_min = config["defect_pa_min"]
    if pa_available and defect_pa_min is not None and phoneme_accuracy is not None and phoneme_accuracy < defect_pa_min:
        capped_score = min(scores["final_score"], weights.rule_severe_pa_score_cap)
        scores = {**scores, "final_score": round(capped_score, 2), "adaptive_decision": "drop", "pass_fail": "fail", "performance_level": "needs_improvement"}

    # Prompt-level advance threshold override
    prompt_threshold = config["prompt_advance_threshold"]
    if prompt_threshold is not None and scores["adaptive_decision"] == "advance":
        if scores["final_score"] < prompt_threshold:
            scores = {**scores, "adaptive_decision": "stay", "pass_fail": "pass", "performance_level": "satisfactory"}

    # Non-terminal failures stay at current level
    if scores["pass_fail"] == "fail" and ctx["attempt_number"] < MAX_ATTEMPTS_PER_PROMPT:
        scores = {**scores, "adaptive_decision": "stay"}

    low_confidence = avg_confidence < weights.rule_low_conf_threshold
    review_recommended = needs_asr_review(transcript, target_text, avg_confidence, word_accuracy)
    fail_reason = "ASR transcript needs review" if review_recommended else None

    return {
        "word_accuracy": word_accuracy,
        "phoneme_accuracy": phoneme_accuracy,
        "pa_available": pa_available,
        "fluency_score": fluency_score,
        "speech_rate_wpm": as_int(round(wpm)),
        "speech_rate_score": speech_rate_score,
        "confidence_score": confidence_score,
        "rl_score": rl_score,
        "tc_score": tc_score,
        "aq_score": aq_score,
        "emotion_score": emotion_score,
        "dominant_emotion": dominant_emotion,
        "behavioral_score": as_float(scores["behavioral_score"]),
        "engagement_score": as_float(scores["engagement_score"]),
        "speech_score": as_float(scores["speech_score"]),
        "final_score": as_float(scores["final_score"]),
        "adaptive_decision": scores["adaptive_decision"],
        "pass_fail": scores["pass_fail"],
        "performance_level": scores["performance_level"],
        "low_confidence": low_confidence,
        "review_recommended": review_recommended,
        "fail_reason": fail_reason,
        "disfluency_rate": as_float(ml["disfluency_result"]["disfluency_rate"]),
        "pause_score": as_float(ml["disfluency_result"]["pause_score"]),
        "target_phoneme_results": json.dumps(ml["phoneme_result"].get("target_phoneme_results") or {}),
        "transcript": transcript,
        "duration": duration,
    }


# ---------------------------------------------------------------------------
# Persist results + queue + WS publish
# ---------------------------------------------------------------------------

def _persist_and_publish(conn, ctx: dict, config: dict, scores: dict) -> None:
    """Write score detail, update progress, handle queue, and publish WS event."""
    cur = conn.cursor()
    attempt_id = str(ctx["attempt_id"])
    session_id = str(ctx["session_id"])
    patient_id = str(ctx["patient_id"])
    attempt_number = ctx["attempt_number"]
    level_id = ctx["level_id"]
    task_id = ctx["task_id"]
    assigned_therapist_id = config["assigned_therapist_id"]

    insert_score_detail(cur, (
        str(uuid.uuid4()), attempt_id,
        scores["word_accuracy"], scores["phoneme_accuracy"], scores["pa_available"],
        scores["fluency_score"], scores["disfluency_rate"], scores["pause_score"],
        scores["speech_rate_wpm"], scores["speech_rate_score"], scores["confidence_score"],
        scores["rl_score"], scores["tc_score"], scores["aq_score"],
        scores["behavioral_score"], scores["dominant_emotion"], scores["emotion_score"],
        scores["engagement_score"], scores["speech_score"], scores["final_score"],
        scores["adaptive_decision"], scores["pass_fail"],
        scores["fail_reason"], scores["performance_level"],
        scores["low_confidence"], scores["review_recommended"],
        scores["transcript"], scores["duration"],
        scores["target_phoneme_results"],
    ))

    cur.execute(
        "UPDATE session_prompt_attempt SET result=%s, asr_transcript=%s, speech_detected=true"
        " WHERE attempt_id=%s",
        (scores["pass_fail"], scores["transcript"], attempt_id),
    )

    # Session queue handling
    notes, queue_active, queue_override = apply_session_queue_result(
        cur, session_id, str(task_id) if task_id else "",
        str(ctx["prompt_id"]), scores["pass_fail"], attempt_number,
        level_id, scores["fail_reason"], scores["final_score"],
        patient_id, str(assigned_therapist_id) if assigned_therapist_id else None,
        attempt_id,
    )

    adaptive_decision = scores["adaptive_decision"]
    performance_level = scores["performance_level"]
    if queue_override:
        adaptive_decision = queue_override.get("adaptive_decision", adaptive_decision)
        performance_level = queue_override.get("performance_level", performance_level)
        cur.execute(
            "UPDATE attempt_score_detail SET adaptive_decision=%s, performance_level=%s WHERE attempt_id=%s",
            (adaptive_decision, performance_level, attempt_id),
        )

    progress_decision = adaptive_decision
    if queue_active and scores["pass_fail"] == "pass":
        progress_decision = "stay"

    upsert_patient_task_progress(
        cur, patient_id, task_id, level_id,
        progress_decision, scores["final_score"], scores["pass_fail"],
    )
    mark_prompt_terminal(cur, session_id, ctx["prompt_id"], scores["pass_fail"], attempt_number)
    upsert_session_emotion_summary(cur, session_id, patient_id)

    if scores["review_recommended"] and assigned_therapist_id:
        create_review_notification(cur, assigned_therapist_id, patient_id, attempt_id)

    conn.commit()

    # Escalation → plan regeneration
    if adaptive_decision == "escalated" and assigned_therapist_id:
        escalation_history = notes.get("adaptation_history") or []
        escalation_level = (
            escalation_history[0].get("from_level")
            if escalation_history
            else (notes.get("escalation_level") or get_level_name_from_level_id(cur, level_id))
        )
        if escalation_level:
            regenerate_plan_after_escalation.delay(
                patient_id, str(assigned_therapist_id), str(escalation_level),
            )

    # Publish WebSocket event
    payload = build_ws_payload(
        attempt_id, attempt_number, scores["transcript"],
        scores["word_accuracy"], scores["phoneme_accuracy"], scores["pa_available"],
        scores["fluency_score"], scores["speech_rate_wpm"], scores["speech_rate_score"],
        scores["confidence_score"], scores["speech_score"], scores["behavioral_score"],
        scores["engagement_score"], scores["emotion_score"], scores["final_score"],
        scores["pass_fail"], adaptive_decision, performance_level,
        scores["dominant_emotion"], scores["review_recommended"], scores["fail_reason"],
    )
    publish_score_event(patient_id, payload)


# ---------------------------------------------------------------------------
# No-speech fast path
# ---------------------------------------------------------------------------

def _handle_no_speech(conn, ctx: dict, config: dict) -> None:
    """Handle the case where no valid speech was detected."""
    cur = conn.cursor()
    attempt_id = str(ctx["attempt_id"])
    session_id = str(ctx["session_id"])
    patient_id = str(ctx["patient_id"])
    attempt_number = ctx["attempt_number"]
    level_id = ctx["level_id"]
    task_id = ctx["task_id"]
    transcript = ""
    duration = 0.0
    assigned_therapist_id = config["assigned_therapist_id"]

    adaptive_decision = "drop" if attempt_number >= MAX_ATTEMPTS_PER_PROMPT else "stay"

    insert_score_detail(cur, (
        str(uuid.uuid4()), attempt_id, 0.0, None, False, 0.0,
        0.0, 0.0, 0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0, "neutral", 0.0,
        0.0, 0.0, 0.0, adaptive_decision, "fail",
        "No speech detected", "needs_improvement", True, True, transcript, duration,
        "{}",
    ))

    cur.execute(
        "UPDATE session_prompt_attempt SET result=%s, asr_transcript=%s, speech_detected=false"
        " WHERE attempt_id=%s",
        ("fail", transcript, attempt_id),
    )
    mark_prompt_terminal(cur, session_id, ctx["prompt_id"], "fail", attempt_number)

    notes, queue_active, queue_override = apply_session_queue_result(
        cur, session_id, str(task_id) if task_id else "",
        str(ctx["prompt_id"]), "fail", attempt_number,
        level_id, "No speech detected", 0.0,
        patient_id, str(assigned_therapist_id) if assigned_therapist_id else None,
        attempt_id,
    )

    if queue_override:
        adaptive_decision = queue_override.get("adaptive_decision", adaptive_decision)
        cur.execute(
            "UPDATE attempt_score_detail SET adaptive_decision=%s, performance_level=%s WHERE attempt_id=%s",
            (adaptive_decision, "needs_improvement", attempt_id),
        )

    progress_decision = adaptive_decision if adaptive_decision != "escalated" else adaptive_decision
    upsert_patient_task_progress(cur, patient_id, task_id, level_id, progress_decision, 0.0, "fail")
    upsert_session_emotion_summary(cur, session_id, patient_id)

    if assigned_therapist_id:
        create_review_notification(cur, assigned_therapist_id, patient_id, attempt_id)

    conn.commit()

    # Escalation → plan regeneration
    if adaptive_decision == "escalated" and assigned_therapist_id:
        escalation_history = notes.get("adaptation_history") or []
        escalation_level = (
            escalation_history[0].get("from_level")
            if escalation_history
            else (notes.get("escalation_level") or get_level_name_from_level_id(cur, level_id))
        )
        if escalation_level:
            regenerate_plan_after_escalation.delay(
                patient_id, str(assigned_therapist_id), str(escalation_level),
            )

    payload = build_ws_payload(
        attempt_id, attempt_number, transcript,
        0.0, None, False, 0.0, 0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0,
        0.0, "fail", adaptive_decision, "needs_improvement", "neutral",
        True, "No speech detected",
    )
    publish_score_event(patient_id, payload)


# ---------------------------------------------------------------------------
# Retry guard: skip already-escalated sessions
# ---------------------------------------------------------------------------

def _is_already_escalated(attempt_number: int, session_id: str) -> bool:
    if attempt_number < MAX_ATTEMPTS_PER_PROMPT:
        return False
    conn = _get_conn()
    try:
        cur = conn.cursor()
        notes = read_session_notes(cur, str(session_id))
        return bool(notes.get("escalated"))
    finally:
        conn.close()


def _publish_escalated_stub(attempt_id: str, attempt_number: int, patient_id: str) -> None:
    payload = build_ws_payload(
        attempt_id, attempt_number, "",
        0.0, None, False, 0.0, 0, 0.0, 0.0,
        0.0, 0.0, 0.0, 0.0,
        0.0, "fail", "escalated", "needs_improvement", "neutral",
        False, None,
    )
    publish_score_event(str(patient_id), payload)


# ===========================================================================
# CELERY TASK — slim orchestrator
# ===========================================================================

@celery_app.task(name="app.tasks.analysis.analyze_attempt", bind=True, max_retries=2)
def analyze_attempt(self, attempt_id):
    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()

        # 1. Load context
        ctx = _load_attempt_context(cur, attempt_id)
        if not ctx:
            return

        if not ctx["audio_path"] or not os.path.exists(ctx["audio_path"]):
            cur.execute("UPDATE session_prompt_attempt SET result='fail' WHERE attempt_id=%s", (attempt_id,))
            conn.commit()
            return

        # 2. Load scoring config
        config = _load_scoring_config(cur, ctx["task_id"], ctx["patient_id"], ctx["prompt_id"])
        conn.close()
        conn = None

        # 3. Retry guard — skip if session already escalated
        if _is_already_escalated(ctx["attempt_number"], ctx["session_id"]):
            _publish_escalated_stub(attempt_id, ctx["attempt_number"], ctx["patient_id"])
            return

        # 4. Resolve target text
        target_text = ctx["target_response"]
        if not target_text and ctx.get("speech_target") and isinstance(ctx["speech_target"], dict):
            target_text = ctx["speech_target"].get("text")

        # 5. Run ML pipeline
        ml = _run_ml_pipeline(ctx["audio_path"], target_text)

        # 5a. Update phoneme result with prompt-specific target phonemes
        target_phonemes = parse_target_phonemes(ctx["prompt_target_phonemes"])
        if target_phonemes:
            from app.ml.hubert_phoneme import align_phonemes
            ml["phoneme_result"] = align_phonemes(
                ctx["audio_path"], ml["transcript"],
                target_phonemes=target_phonemes,
                reference_text=target_text,
            )

        # 6. No-speech check
        if is_no_speech(ml["transcript"], ml["duration"], ml["avg_confidence"]):
            conn = _get_conn()
            _handle_no_speech(conn, ctx, config)
            return

        # 7. Compute scores
        scores = _compute_all_scores(ctx, config, ml)

        # 8. Persist + publish
        conn = _get_conn()
        _persist_and_publish(conn, ctx, config, scores)

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
