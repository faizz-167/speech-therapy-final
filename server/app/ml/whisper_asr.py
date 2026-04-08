from functools import lru_cache
import warnings


@lru_cache(maxsize=1)
def _load_model():
    try:
        import torch
        import whisper
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Whisper ASR dependency is not installed. Install 'openai-whisper' in the server environment."
        ) from exc
    device = "cuda" if torch.cuda.is_available() else "cpu"
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=r".*torch\.load.*weights_only=False.*",
            category=FutureWarning,
        )
        return whisper.load_model("small", device=device)


def transcribe(audio_path: str, expected_text: str | None = None) -> dict:
    """Returns {transcript, words, duration, avg_confidence}"""
    model = _load_model()
    initial_prompt = None
    if expected_text:
        # Truncate to 200 chars and strip newlines to prevent prompt injection via DB content.
        safe_hint = expected_text[:200].replace("\n", " ").replace("\r", " ")
        initial_prompt = f"Transcribe spoken English. Style hint: {safe_hint}"

    result = model.transcribe(
        audio_path,
        task="transcribe",
        language="en",
        word_timestamps=True,
        condition_on_previous_text=False,
        temperature=0,
        no_speech_threshold=0.6,
        compression_ratio_threshold=2.0,
        logprob_threshold=-1.0,
        initial_prompt=initial_prompt,
    )
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
