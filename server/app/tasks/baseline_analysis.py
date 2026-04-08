"""Celery task: score a single baseline audio attempt using the ML pipeline."""
import os
import uuid

import psycopg2

from app.celery_app import celery_app
from app.config import settings


def _get_conn():
    return psycopg2.connect(settings.database_url_sync)


def _as_float(value, default: float = 0.0) -> float:
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _compute_speech_rate_score(wpm: float, ideal_min: int = 80, ideal_max: int = 120, tolerance: int = 20) -> float:
    if ideal_min <= wpm <= ideal_max:
        return 100.0
    if wpm < ideal_min:
        diff = ideal_min - wpm
        return max(0.0, 100.0 - (diff / tolerance) * 30)
    diff = wpm - ideal_max
    return max(0.0, 100.0 - (diff / tolerance) * 30)


def _baseline_score(formula_mode: str, pa: float, wa: float, fs: float,
                    wpm: float, formula_weights: dict | None, wpm_range: dict | None) -> float:
    """Compute a 0–100 baseline score according to formula_mode."""
    if formula_mode == "auto_phoneme_only":
        fw = formula_weights or {"pa": 0.80, "wa": 0.20}
        score = pa * fw.get("pa", 0.80) + wa * fw.get("wa", 0.20)
    elif formula_mode == "auto_simple":
        fw = formula_weights or {"pa": 0.50, "wa": 0.30, "fs": 0.20}
        score = pa * fw.get("pa", 0.50) + wa * fw.get("wa", 0.30) + fs * fw.get("fs", 0.20)
        if wpm_range:
            ideal_min = wpm_range.get("min", 0)
            ideal_max = wpm_range.get("max", 999)
            if wpm > 0 and not (ideal_min <= wpm <= ideal_max):
                score = max(0.0, score - 10.0)
    else:
        score = (pa + wa) / 2.0
    return round(min(100.0, max(0.0, score)), 2)


@celery_app.task(name="app.tasks.baseline_analysis.analyze_baseline_attempt", bind=True, max_retries=2)
def analyze_baseline_attempt(self, attempt_id: str):
    """Score a baseline audio attempt and update the baseline_attempt row."""
    conn = None
    try:
        from app.ml.whisper_asr import transcribe
        from app.ml.hubert_phoneme import align_phonemes
        from app.ml.spacy_disfluency import score_disfluency
        from app.ml.speechbrain_emotion import classify_emotion

        conn = _get_conn()
        cur = conn.cursor()

        cur.execute(
            "SELECT ba.attempt_id, ba.audio_file_path, ba.item_id,"
            " bi.formula_mode, bi.formula_weights, bi.wpm_range, bi.expected_output"
            " FROM baseline_attempt ba"
            " JOIN baseline_item bi ON bi.item_id = ba.item_id"
            " WHERE ba.attempt_id = %s",
            (attempt_id,),
        )
        row = cur.fetchone()
        if not row:
            return

        attempt_id_db, audio_path, item_id, formula_mode, formula_weights, wpm_range, expected_output = row

        if not audio_path or not os.path.exists(audio_path):
            cur.execute(
                "UPDATE baseline_attempt SET result='failed' WHERE attempt_id=%s",
                (attempt_id,),
            )
            conn.commit()
            return

        conn.close()
        conn = None

        asr = transcribe(audio_path, expected_text=expected_output)
        transcript = asr["transcript"]
        duration = _as_float(asr["duration"])
        avg_confidence = _as_float(asr["avg_confidence"])

        phoneme_result = align_phonemes(audio_path, transcript)
        disfluency_result = score_disfluency(transcript, duration)
        emotion_result = classify_emotion(audio_path)

        pa = _as_float(phoneme_result["phoneme_accuracy"], 70.0)
        fs = _as_float(disfluency_result["fluency_score"], 50.0)
        wpm = _as_float((len(transcript.split()) / duration * 60) if duration > 0 else 0)
        speech_rate_score = _compute_speech_rate_score(wpm)
        dominant_emotion = emotion_result.get("dominant_emotion") or "neutral"
        emotion_score = _as_float(emotion_result.get("emotion_score"), 60.0)
        engagement_score = _as_float(emotion_result.get("engagement_score"), 60.0)

        wa = 75.0
        if expected_output and transcript:
            target_words = {w.strip(".,!?;:").lower() for w in expected_output.split()}
            spoken_words = {w.strip(".,!?;:").lower() for w in transcript.split()}
            if target_words:
                wa = round(len(target_words & spoken_words) / len(target_words) * 100, 2)

        computed = _baseline_score(formula_mode or "auto_simple", pa, wa, fs, wpm, formula_weights, wpm_range)
        wpm_int = int(round(wpm))

        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE baseline_attempt"
            " SET result='scored', ml_phoneme_accuracy=%s, ml_word_accuracy=%s,"
            " ml_fluency_score=%s, ml_speech_rate_wpm=%s, ml_speech_rate_score=%s,"
            " ml_confidence=%s, dominant_emotion=%s, emotion_score=%s, engagement_score=%s,"
            " asr_transcript=%s, computed_score=%s"
            " WHERE attempt_id=%s",
            (
                pa,
                wa,
                fs,
                wpm_int,
                round(speech_rate_score, 2),
                round(avg_confidence * 100, 2),
                dominant_emotion,
                emotion_score,
                engagement_score,
                transcript,
                computed,
                attempt_id,
            ),
        )
        conn.commit()

    except RuntimeError as exc:
        try:
            if conn is None or conn.closed:
                conn = _get_conn()
            cur = conn.cursor()
            cur.execute(
                "UPDATE baseline_attempt SET result='failed', asr_transcript=%s WHERE attempt_id=%s",
                (str(exc), attempt_id),
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
