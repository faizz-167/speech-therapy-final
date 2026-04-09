from functools import lru_cache

EMOTION_MAP = {"ang": "angry", "hap": "happy", "sad": "sad", "neu": "neutral"}
ENGAGEMENT_MULTIPLIERS = {
    "happy": 1.0,
    "excited": 1.0,
    "surprised": 0.85,
    "neutral": 0.6,
    "sad": 0.35,
    "angry": 0.25,
    "fearful": 0.3,
}


@lru_cache(maxsize=1)
def _load_classifier():
    from speechbrain.pretrained import EncoderClassifier
    return EncoderClassifier.from_hparams(
        source="speechbrain/emotion-recognition-wav2vec2-IEMOCAP",
        savedir="tmp_emotion_model",
    )


def _to_scalar(value, default: float = 0.0) -> float:
    if value is None:
        return default
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            return default
    if isinstance(value, (list, tuple)):
        if not value:
            return default
        return _to_scalar(value[0], default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def classify_emotion(audio_path: str) -> dict:
    """Returns {dominant_emotion, emotion_score, engagement_score}"""
    try:
        classifier = _load_classifier()
        out_prob, score, index, label = classifier.classify_file(audio_path)
        raw_label = label[0] if label else None
        dominant_emotion = EMOTION_MAP.get(raw_label, raw_label)
        confidence = _to_scalar(score)
        if confidence <= 0.0 and out_prob is not None and index is not None:
            try:
                confidence = _to_scalar(out_prob[0][int(_to_scalar(index))])
            except Exception:
                confidence = 0.0
        confidence = min(1.0, max(0.0, confidence))
        emotion_score = round(confidence * 100, 2)
        engagement_multiplier = ENGAGEMENT_MULTIPLIERS.get(dominant_emotion or "", 0.5)
        engagement_score = round(emotion_score * engagement_multiplier, 2)
        engagement_score = min(100.0, engagement_score)
        return {
            "dominant_emotion": dominant_emotion,
            "emotion_score": emotion_score,
            "engagement_score": engagement_score,
            "confidence": round(confidence, 4),
            "inference_ok": True,
        }
    except Exception:
        return {
            "dominant_emotion": None,
            "emotion_score": 0.0,
            "engagement_score": 0.0,
            "confidence": 0.0,
            "inference_ok": False,
        }
