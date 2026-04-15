from functools import lru_cache
import logging
import os
from pathlib import Path
import subprocess
import tempfile

import torchaudio


logger = logging.getLogger(__name__)

EMOTION_MAP = {"ang": "angry", "hap": "happy", "sad": "sad", "neu": "neutral"}
RAW_EMOTION_LABELS = ("ang", "hap", "neu", "sad")
ENGAGEMENT_MULTIPLIERS = {
    "happy": 1.0,
    "excited": 1.0,
    "surprised": 0.85,
    "neutral": 0.6,
    "sad": 0.35,
    "angry": 0.25,
    "fearful": 0.3,
}
TARGET_SAMPLE_RATE = 16000


def _clear_dead_local_proxy() -> None:
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        value = os.environ.get(key, "")
        if "127.0.0.1:9" in value or "localhost:9" in value:
            os.environ.pop(key, None)


def _force_speechbrain_copy_fetch(local_strategy) -> None:
    from speechbrain.utils.parameter_transfer import Pretrainer

    if getattr(Pretrainer.collect_files, "_speechpath_copy_patch", False):
        return

    original_collect_files = Pretrainer.collect_files

    def collect_files_with_copy(self, *args, **kwargs):
        kwargs.setdefault("local_strategy", local_strategy)
        return original_collect_files(self, *args, **kwargs)

    collect_files_with_copy._speechpath_copy_patch = True
    Pretrainer.collect_files = collect_files_with_copy


@lru_cache(maxsize=1)
def _load_classifier():
    from speechbrain.inference.interfaces import foreign_class
    from speechbrain.utils.fetching import LocalStrategy

    _clear_dead_local_proxy()
    _force_speechbrain_copy_fetch(LocalStrategy.COPY)
    return foreign_class(
        source="speechbrain/emotion-recognition-wav2vec2-IEMOCAP",
        pymodule_file="custom_interface.py",
        classname="CustomEncoderWav2vec2Classifier",
        savedir="tmp_emotion_model",
        local_strategy=LocalStrategy.COPY,
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


def _to_list(value) -> list:
    if value is None:
        return []
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "squeeze"):
        value = value.squeeze()
    if hasattr(value, "tolist"):
        try:
            value = value.tolist()
        except Exception:
            return []
    if isinstance(value, list):
        if value and isinstance(value[0], list):
            return value[0]
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _first_label(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)) and value:
        return _first_label(value[0])
    if hasattr(value, "item"):
        try:
            return str(value.item())
        except Exception:
            return None
    return str(value)


def _label_lookup(classifier) -> dict[int, str]:
    label_encoder = getattr(getattr(classifier, "hparams", None), "label_encoder", None)
    labels = getattr(label_encoder, "ind2lab", None)
    if isinstance(labels, dict):
        return {int(index): str(label) for index, label in labels.items()}
    if isinstance(labels, (list, tuple)):
        return {index: str(label) for index, label in enumerate(labels)}
    return {index: label for index, label in enumerate(RAW_EMOTION_LABELS)}


def _probability_dict(classifier, out_prob) -> dict[str, float]:
    probabilities = _to_list(out_prob)
    labels = _label_lookup(classifier)
    return {
        labels.get(index, str(index)): min(1.0, max(0.0, _to_scalar(probability)))
        for index, probability in enumerate(probabilities)
    }


def _convert_audio_with_ffmpeg(audio_path: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
        tmp_path = handle.name
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                audio_path,
                "-ac",
                "1",
                "-ar",
                str(TARGET_SAMPLE_RATE),
                tmp_path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    return tmp_path


def _prepare_audio_for_classifier(audio_path: str) -> str:
    try:
        waveform, sample_rate = torchaudio.load(audio_path)
    except Exception:
        return _convert_audio_with_ffmpeg(audio_path)

    if waveform.ndim == 1:
        waveform = waveform.unsqueeze(0)
    if waveform.size(0) > 1:
        waveform = waveform.mean(dim=0, keepdim=True)
    if sample_rate != TARGET_SAMPLE_RATE:
        waveform = torchaudio.functional.resample(waveform, sample_rate, TARGET_SAMPLE_RATE)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
        tmp_path = handle.name
    torchaudio.save(tmp_path, waveform.cpu(), TARGET_SAMPLE_RATE)
    return tmp_path


def classify_emotion(audio_path: str) -> dict:
    """Classify emotion using the same SpeechBrain path as Emotion_analysis.ipynb."""
    prepared_path = None
    try:
        classifier = _load_classifier()
        prepared_path = _prepare_audio_for_classifier(audio_path)
        classifier_input_path = Path(prepared_path).resolve().as_posix()
        out_prob, score, index, text_lab = classifier.classify_file(classifier_input_path)
        probabilities = _probability_dict(classifier, out_prob)
        raw_label = _first_label(text_lab)
        if not raw_label and probabilities:
            raw_label = max(probabilities, key=probabilities.get)
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
            "raw_label": raw_label,
            "emotion_probabilities": probabilities,
            "inference_ok": True,
        }
    except Exception as exc:
        logger.warning("Emotion inference failed for %s: %s", audio_path, exc)
        return {
            "dominant_emotion": None,
            "emotion_score": 0.0,
            "engagement_score": 0.0,
            "confidence": 0.0,
            "inference_ok": False,
        }
    finally:
        if prepared_path and os.path.exists(prepared_path):
            try:
                os.remove(prepared_path)
            except OSError:
                logger.warning("Could not remove temp emotion audio file: %s", prepared_path)
