from functools import lru_cache

EMOTION_MAP = {"ang": "angry", "hap": "happy", "sad": "sad", "neu": "neutral"}
POSITIVE_EMOTIONS = {"happy", "excited", "neutral"}


@lru_cache(maxsize=1)
def _load_classifier():
    from speechbrain.pretrained import EncoderClassifier
    return EncoderClassifier.from_hparams(
        source="speechbrain/emotion-recognition-wav2vec2-IEMOCAP",
        savedir="tmp_emotion_model",
    )


def classify_emotion(audio_path: str) -> dict:
    """Returns {dominant_emotion, emotion_score, engagement_score}"""
    try:
        classifier = _load_classifier()
        out_prob, score, index, label = classifier.classify_file(audio_path)
        raw_label = label[0] if label else "neu"
        dominant_emotion = EMOTION_MAP.get(raw_label, raw_label)
        confidence = float(score[0]) if score else 0.5
        is_positive = dominant_emotion in POSITIVE_EMOTIONS
        emotion_score = round(confidence * 100, 2)
        engagement_score = round(emotion_score * (1.2 if is_positive else 0.7), 2)
        engagement_score = min(100.0, engagement_score)
        return {"dominant_emotion": dominant_emotion, "emotion_score": emotion_score, "engagement_score": engagement_score}
    except Exception:
        return {"dominant_emotion": "neutral", "emotion_score": 60.0, "engagement_score": 60.0}
