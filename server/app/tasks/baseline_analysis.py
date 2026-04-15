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
    if wpm <= 0:
        return 0.0
    tolerance = max(1, tolerance)
    if ideal_min <= wpm <= ideal_max:
        return 100.0
    if wpm < ideal_min:
        diff = ideal_min - wpm
    else:
        diff = wpm - ideal_max

    if diff <= tolerance:
        return round(100.0 - ((diff / tolerance) * 25.0), 2)
    if diff <= tolerance * 2:
        return round(75.0 - (((diff - tolerance) / tolerance) * 35.0), 2)
    return round(max(0.0, 40.0 - (((diff - (tolerance * 2)) / (tolerance * 2)) * 40.0)), 2)


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


def _weighted_score(components: list[tuple[float, float, bool]]) -> float:
    active = [(value, weight) for value, weight, available in components if available and weight > 0]
    if not active:
        return 0.0
    total_weight = sum(weight for _, weight in active)
    if total_weight <= 0:
        return 0.0
    return sum(value * weight for value, weight in active) / total_weight


def _parse_target_phonemes(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _baseline_score(formula_mode: str, pa: float | None, wa: float, fs: float,
                    wpm: float, formula_weights: dict | None, wpm_range: dict | None,
                    pa_available: bool = True, wa_available: bool = True) -> float:
    """Compute a 0–100 baseline score according to formula_mode."""
    if formula_mode == "auto_phoneme_only":
        fw = formula_weights or {"pa": 0.80, "wa": 0.20}
        score = _weighted_score([
            (pa if pa is not None else 0.0, fw.get("pa", 0.80), pa_available),
            (wa, fw.get("wa", 0.20), wa_available),
        ])
    elif formula_mode == "auto_simple":
        fw = formula_weights or {"pa": 0.50, "wa": 0.30, "fs": 0.20}
        score = _weighted_score([
            (pa if pa is not None else 0.0, fw.get("pa", 0.50), pa_available),
            (wa, fw.get("wa", 0.30), wa_available),
            (fs, fw.get("fs", 0.20), True),
        ])
        if wpm_range:
            ideal_min = wpm_range.get("min", 0)
            ideal_max = wpm_range.get("max", 999)
            if wpm > 0 and not (ideal_min <= wpm <= ideal_max):
                score = max(0.0, score - 10.0)
    else:
        components = []
        if pa_available and pa is not None:
            components.append(pa)
        if wa_available:
            components.append(wa)
        score = sum(components) / len(components) if components else 0.0
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
            " bi.formula_mode, bi.formula_weights, bi.wpm_range, bi.expected_output, bi.target_phoneme"
            " FROM baseline_attempt ba"
            " JOIN baseline_item bi ON bi.item_id = ba.item_id"
            " WHERE ba.attempt_id = %s",
            (attempt_id,),
        )
        row = cur.fetchone()
        if not row:
            return

        attempt_id_db, audio_path, item_id, formula_mode, formula_weights, wpm_range, expected_output, target_phoneme = row

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
        words = asr.get("words") or []

        phoneme_result = align_phonemes(
            audio_path,
            transcript,
            target_phonemes=_parse_target_phonemes(target_phoneme),
            reference_text=expected_output,
        )
        disfluency_result = score_disfluency(transcript, duration, words)
        emotion_result = classify_emotion(audio_path)

        pa_available = bool(phoneme_result.get("inference_ok"))
        pa = _as_float(phoneme_result.get("phoneme_accuracy"), 0.0) if pa_available else None
        fs = _as_float(disfluency_result["fluency_score"], 50.0)
        wpm = _as_float(_compute_speech_rate_wpm(transcript, duration, words))
        speech_rate_range = wpm_range if isinstance(wpm_range, dict) else {}
        speech_rate_score = _compute_speech_rate_score(
            wpm,
            int(speech_rate_range.get("min", 80)),
            int(speech_rate_range.get("max", 120)),
            int(speech_rate_range.get("tolerance", 20)),
        )
        dominant_emotion = emotion_result.get("dominant_emotion")
        emotion_score = _as_float(emotion_result.get("emotion_score"), 0.0)
        engagement_score = _as_float(emotion_result.get("engagement_score"), 0.0)

        wa_available = bool(expected_output)
        wa = 0.0
        if wa_available and transcript:
            target_words = {w.strip(".,!?;:").lower() for w in expected_output.split()}
            spoken_words = {w.strip(".,!?;:").lower() for w in transcript.split()}
            if target_words:
                wa = round(len(target_words & spoken_words) / len(target_words) * 100, 2)

        computed = _baseline_score(
            formula_mode or "auto_simple",
            pa,
            wa,
            fs,
            wpm,
            formula_weights,
            wpm_range,
            pa_available=pa_available,
            wa_available=wa_available,
        )
        wpm_int = int(round(wpm))

        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE baseline_attempt"
            " SET result='scored', ml_phoneme_accuracy=%s, pa_available=%s, ml_word_accuracy=%s,"
            " ml_fluency_score=%s, ml_speech_rate_wpm=%s, ml_speech_rate_score=%s,"
            " ml_confidence=%s, dominant_emotion=%s, emotion_score=%s, engagement_score=%s,"
            " asr_transcript=%s, computed_score=%s"
            " WHERE attempt_id=%s",
            (
                pa,
                pa_available,
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
