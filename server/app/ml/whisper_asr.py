import whisper
import torch
from functools import lru_cache


@lru_cache(maxsize=1)
def _load_model():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return whisper.load_model("small", device=device)


def transcribe(audio_path: str) -> dict:
    """Returns {transcript, words, duration, avg_confidence}"""
    model = _load_model()
    result = model.transcribe(audio_path, word_timestamps=True, language="en")
    tokens = result.get("segments", [])
    all_words = []
    for seg in tokens:
        for word in seg.get("words", []):
            all_words.append({
                "word": word["word"].strip(),
                "start": word["start"],
                "end": word["end"],
                "probability": word.get("probability", 1.0),
            })
    avg_confidence = sum(w["probability"] for w in all_words) / len(all_words) if all_words else 0.0
    duration = result["segments"][-1]["end"] if result["segments"] else 0.0
    return {
        "transcript": result["text"].strip(),
        "words": all_words,
        "duration": duration,
        "avg_confidence": avg_confidence,
    }
