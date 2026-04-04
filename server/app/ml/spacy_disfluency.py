import spacy
from functools import lru_cache

FILLER_WORDS = {"uh", "um", "er", "ah", "like", "you know", "sort of", "kind of"}


@lru_cache(maxsize=1)
def _load_nlp():
    return spacy.load("en_core_web_lg")


def score_disfluency(transcript: str, audio_duration: float = 0.0) -> dict:
    """Returns {disfluency_rate, pause_score, fluency_score}"""
    if not transcript.strip():
        return {"disfluency_rate": 0.0, "pause_score": 50.0, "fluency_score": 50.0}
    nlp = _load_nlp()
    doc = nlp(transcript.lower())
    words = [t.text for t in doc if not t.is_punct]
    total_words = len(words)
    if total_words == 0:
        return {"disfluency_rate": 0.0, "pause_score": 50.0, "fluency_score": 50.0}
    filler_count = sum(1 for w in words if w in FILLER_WORDS)
    disfluency_rate = round((filler_count / total_words) * 100, 2)
    wpm = (total_words / audio_duration * 60) if audio_duration > 1 else 100
    fluency_score = max(0.0, min(100.0, 100.0 - (disfluency_rate * 2)))
    pause_score = min(100.0, max(0.0, 100.0 - max(0, wpm - 180) * 0.5))
    return {
        "disfluency_rate": disfluency_rate,
        "pause_score": round(pause_score, 2),
        "fluency_score": round(fluency_score, 2),
    }
