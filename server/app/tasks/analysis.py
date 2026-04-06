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


def _compute_speech_rate_score(wpm, ideal_min=80, ideal_max=120, tolerance=20):
    if ideal_min <= wpm <= ideal_max:
        return 100.0
    elif wpm < ideal_min:
        diff = ideal_min - wpm
        return max(0.0, 100.0 - (diff / tolerance) * 30)
    else:
        diff = wpm - ideal_max
        return max(0.0, 100.0 - (diff / tolerance) * 30)


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


_SCORE_INSERT_SQL = (
    "INSERT INTO attempt_score_detail ("
    " detail_id, attempt_id, word_accuracy, phoneme_accuracy, fluency_score,"
    " disfluency_rate, pause_score, speech_rate_wpm, speech_rate_score, confidence_score,"
    " rl_score, tc_score, aq_score, behavioral_score, dominant_emotion, emotion_score,"
    " engagement_score, speech_score, final_score, adaptive_decision, pass_fail,"
    " fail_reason, performance_level, low_confidence_flag, review_recommended, asr_transcript, audio_duration_sec,"
    " target_phoneme_results, created_at"
    ") VALUES ("
    " %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW()"
    ")"
)


def _exec_insert_score_detail(cur, params: tuple) -> None:
    cur.execute(_SCORE_INSERT_SQL, params)


def _build_ws_payload(
    attempt_id: str,
    attempt_number: int,
    transcript: str,
    wa: float, pa: float, fs: float,
    wpm: int, srs: float, cs: float,
    speech_score: float, behavioral_score: float, engagement_score: float,
    final_score: float, pass_fail: str, adaptive_decision: str,
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
        "word_accuracy": wa,
        "phoneme_accuracy": pa,
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


@celery_app.task(name="app.tasks.analysis.analyze_attempt", bind=True, max_retries=2)
def analyze_attempt(self, attempt_id):
    # Lazy ML imports — only loaded when the worker actually runs the task
    from app.ml.whisper_asr import transcribe
    from app.ml.hubert_phoneme import align_phonemes
    from app.ml.spacy_disfluency import score_disfluency
    from app.ml.speechbrain_emotion import classify_emotion

    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()

        cur.execute(
            "SELECT spa.attempt_id, spa.attempt_number, spa.session_id, spa.prompt_id, spa.audio_file_path,"
            " spa.mic_activated_at, spa.speech_start_at, spa.task_mode, spa.prompt_type,"
            " p.display_content, p.target_response, p.level_id,"
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
            display_content, target_response, level_id,
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

        conn.close()
        conn = None

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
            _exec_insert_score_detail(
                cur,
                (
                    str(uuid.uuid4()), attempt_id, 0.0, 0.0, 0.0,
                    0.0, 0.0, 0, 0.0, 0.0,
                    0.0, 0.0, 0.0, 0.0, "neutral", 0.0,
                    0.0, 0.0, 0.0, "drop", "fail",
                    "No speech detected", "needs_improvement", True, True, transcript, duration,
                    "{}",
                ),
            )
            cur.execute(
                "UPDATE session_prompt_attempt SET result=%s, asr_transcript=%s, speech_detected=false"
                " WHERE attempt_id=%s",
                ("fail", transcript, attempt_id),
            )
            conn.commit()
            r = redis.from_url(settings.redis_url)
            r.publish(
                f"ws:patient:{patient_id}",
                json.dumps(_build_ws_payload(
                    attempt_id, attempt_number, transcript,
                    0.0, 0.0, 0.0, 0, 0.0, 0.0,
                    0.0, 0.0, 0.0,
                    0.0, "fail", "drop", "needs_improvement", "neutral",
                    True, "No speech detected",
                )),
            )
            return

        phoneme_result = align_phonemes(audio_path, transcript)
        disfluency_result = score_disfluency(transcript, duration)
        emotion_result = classify_emotion(audio_path)

        wpm = _as_float((len(transcript.split()) / duration * 60) if duration > 0 else 0)
        # When no target text is available we cannot penalise word accuracy —
        # use a neutral value so the overall score reflects only speech quality.
        if target_text:
            wa = _as_float(_compute_word_accuracy(transcript, target_text), default=0.0)
        else:
            wa = 75.0
        pa = _as_float(phoneme_result["phoneme_accuracy"], default=70.0)
        fs = _as_float(disfluency_result["fluency_score"], default=50.0)
        srs = _as_float(_compute_speech_rate_score(wpm, ideal_wpm_min, ideal_wpm_max, wpm_tolerance))
        cs = _as_float(min(100.0, avg_confidence * 100))
        rl_score = _as_float(_compute_rl_score(str(mic_at) if mic_at else None, str(speech_at) if speech_at else None), default=70.0)
        tc_score = _as_float(_compute_tc_score(transcript, target_word_count, target_duration_sec, duration), default=80.0)
        aq_score = _as_float(_compute_aq_score(transcript), default=30.0)
        emotion_score = _as_float(emotion_result["emotion_score"], default=60.0)
        engagement_score = _as_float(emotion_result["engagement_score"], default=60.0)
        dominant_emotion = emotion_result["dominant_emotion"]

        scores = score_attempt(
            pa=pa, wa=wa, fs=fs, srs=srs, cs=cs,
            rl_score=rl_score, tc_score=tc_score, aq_score=aq_score,
            emotion_score=emotion_score, weights=weights,
        )

        behavioral_score = _as_float(scores["behavioral_score"])
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

        conn = _get_conn()
        cur = conn.cursor()
        wpm_int = _as_int(round(wpm))
        _exec_insert_score_detail(
            cur,
            (
                str(uuid.uuid4()), attempt_id, wa, pa, fs,
                disfluency_rate, pause_score,
                wpm_int, srs, cs,
                rl_score, tc_score, aq_score, behavioral_score, dominant_emotion, emotion_score,
                engagement_score, speech_score, final_score, adaptive_decision, pass_fail,
                fail_reason, performance_level, low_confidence, review_recommended, transcript, duration,
                "{}",
            ),
        )
        cur.execute(
            "UPDATE session_prompt_attempt SET result=%s, asr_transcript=%s, speech_detected=true"
            " WHERE attempt_id=%s",
            (pass_fail, transcript, attempt_id),
        )
        conn.commit()

        r = redis.from_url(settings.redis_url)
        r.publish(
            f"ws:patient:{patient_id}",
            json.dumps(_build_ws_payload(
                attempt_id, attempt_number, transcript,
                wa, pa, fs, wpm_int, srs, cs,
                speech_score, behavioral_score, engagement_score,
                final_score, pass_fail, adaptive_decision, performance_level, dominant_emotion,
                review_recommended, fail_reason,
            )),
        )

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
