import uuid
import os
import json
from datetime import datetime
import psycopg2
import redis

from app.celery_app import celery_app
from app.config import settings
from app.scoring.engine import score_attempt, weights_from_db_row, ScoringWeights


def _get_conn():
    return psycopg2.connect(settings.database_url_sync)


def _compute_word_accuracy(transcript, target_text):
    if not target_text or not transcript:
        return 70.0
    target_words = set(target_text.lower().split())
    spoken_words = set(transcript.lower().split())
    if not target_words:
        return 70.0
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


@celery_app.task(name="app.tasks.analysis.analyze_attempt", bind=True, max_retries=2)
def analyze_attempt(self, attempt_id):
    # Lazy ML imports — only loaded when the worker actually runs the task
    from app.ml.whisper_asr import transcribe
    from app.ml.hubert_phoneme import align_phonemes
    from app.ml.spacy_disfluency import score_disfluency
    from app.ml.speechbrain_emotion import classify_emotion

    conn = _get_conn()
    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT spa.attempt_id, spa.session_id, spa.prompt_id, spa.audio_file_path,"
            " spa.mic_activated_at, spa.speech_start_at, spa.task_mode, spa.prompt_type,"
            " p.display_content, p.target_response, p.level_id,"
            " ps.target_word_count, ps.target_duration_sec, ps.aq_relevance_threshold,"
            " st.raw_speech_target,"
            " tl.task_id,"
            " s.patient_id, s.plan_id"
            " FROM session_prompt_attempt spa"
            " JOIN session s ON s.session_id = spa.session_id"
            " JOIN prompt p ON p.prompt_id = spa.prompt_id"
            " LEFT JOIN prompt_scoring ps ON ps.prompt_id = spa.prompt_id"
            " LEFT JOIN speech_target st ON st.prompt_id = spa.prompt_id"
            " LEFT JOIN task_level tl ON tl.level_id = p.level_id"
            " WHERE spa.attempt_id = %s",
            (attempt_id,),
        )
        row = cur.fetchone()
        if not row:
            return

        (
            attempt_id_db, session_id, prompt_id, audio_path,
            mic_at, speech_at, task_mode, prompt_type,
            display_content, target_response, level_id,
            target_word_count, target_duration_sec, aq_threshold,
            raw_speech_target, task_id, patient_id, plan_id,
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

        asr = transcribe(audio_path)
        transcript = asr["transcript"]
        duration = asr["duration"]
        avg_confidence = asr["avg_confidence"]

        phoneme_result = align_phonemes(audio_path, transcript)
        disfluency_result = score_disfluency(transcript, duration)
        emotion_result = classify_emotion(audio_path)

        wpm = (len(transcript.split()) / duration * 60) if duration > 0 else 0
        target_text = target_response
        if not target_text and raw_speech_target and isinstance(raw_speech_target, dict):
            target_text = raw_speech_target.get("text")

        wa = _compute_word_accuracy(transcript, target_text)
        pa = phoneme_result["phoneme_accuracy"]
        fs = disfluency_result["fluency_score"]
        srs = _compute_speech_rate_score(wpm, ideal_wpm_min, ideal_wpm_max, wpm_tolerance)
        cs = min(100.0, avg_confidence * 100)
        rl_score = _compute_rl_score(str(mic_at) if mic_at else None, str(speech_at) if speech_at else None)
        tc_score = _compute_tc_score(transcript, target_word_count, target_duration_sec, duration)
        aq_score = _compute_aq_score(transcript)
        emotion_score = emotion_result["emotion_score"]
        engagement_score = emotion_result["engagement_score"]
        dominant_emotion = emotion_result["dominant_emotion"]

        scores = score_attempt(
            pa=pa, wa=wa, fs=fs, srs=srs, cs=cs,
            rl_score=rl_score, tc_score=tc_score, aq_score=aq_score,
            emotion_score=emotion_score, weights=weights,
        )

        behavioral_score = scores["behavioral_score"]
        speech_score = scores["speech_score"]
        final_score = scores["final_score"]
        adaptive_decision = scores["adaptive_decision"]
        pass_fail = scores["pass_fail"]
        performance_level = scores["performance_level"]
        low_confidence = avg_confidence < 0.5

        detail_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO attempt_score_detail ("
            " detail_id, attempt_id, word_accuracy, phoneme_accuracy, fluency_score,"
            " disfluency_rate, pause_score, speech_rate_wpm, speech_rate_score, confidence_score,"
            " rl_score, tc_score, aq_score, behavioral_score, dominant_emotion, emotion_score,"
            " engagement_score, speech_score, final_score, adaptive_decision, pass_fail,"
            " performance_level, low_confidence_flag, review_recommended, asr_transcript, audio_duration_sec,"
            " target_phoneme_results, created_at"
            ") VALUES ("
            " %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW()"
            ")",
            (
                detail_id, attempt_id, wa, pa, fs,
                disfluency_result["disfluency_rate"], disfluency_result["pause_score"],
                int(wpm), srs, cs,
                rl_score, tc_score, aq_score, behavioral_score, dominant_emotion, emotion_score,
                engagement_score, speech_score, final_score, adaptive_decision, pass_fail,
                performance_level, low_confidence, low_confidence, transcript, duration,
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
        payload = {
            "type": "score_ready",
            "attempt_id": attempt_id,
            "final_score": final_score,
            "pass_fail": pass_fail,
            "adaptive_decision": adaptive_decision,
            "performance_level": performance_level,
            "dominant_emotion": dominant_emotion,
            "speech_score": speech_score,
            "engagement_score": engagement_score,
            "word_accuracy": wa,
            "phoneme_accuracy": pa,
            "fluency_score": fs,
            "asr_transcript": transcript,
        }
        r.publish(f"ws:patient:{patient_id}", json.dumps(payload))

    except Exception as exc:
        conn.rollback()
        raise self.retry(exc=exc, countdown=5)
    finally:
        conn.close()
