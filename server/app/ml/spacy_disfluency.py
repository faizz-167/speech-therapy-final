import spacy
from functools import lru_cache

FILLER_WORDS = {"uh", "um", "er", "ah", "eh", "hmm", "like"}
FILLER_PHRASES = {("you", "know"), ("sort", "of"), ("kind", "of")}
REVISION_MARKERS = {
    ("i", "mean"),
    ("sorry",),
    ("wait",),
    ("actually",),
    ("no", "i", "mean"),
}
MEANINGFUL_PAUSE_SEC = 0.3
LONG_PAUSE_SEC = 1.0
SEVERE_PAUSE_SEC = 2.0


@lru_cache(maxsize=1)
def _load_nlp():
    for model_name in ("en_core_web_lg", "en_core_web_sm"):
        try:
            return spacy.load(model_name)
        except OSError:
            continue
    # Tokenization is enough for the current filler-word heuristic.
    return spacy.blank("en")


def _normalized_words(transcript: str) -> list[str]:
    nlp = _load_nlp()
    doc = nlp(transcript.lower())
    return [
        t.text.strip(".,!?;:\"'()[]{}")
        for t in doc
        if not t.is_punct and t.text.strip(".,!?;:\"'()[]{}")
    ]


def _count_phrase_matches(words: list[str], phrases: set[tuple[str, ...]]) -> int:
    count = 0
    for phrase in phrases:
        size = len(phrase)
        if size == 0 or len(words) < size:
            continue
        count += sum(1 for idx in range(len(words) - size + 1) if tuple(words[idx:idx + size]) == phrase)
    return count


def _count_repetitions(words: list[str]) -> int:
    repeated_words = sum(1 for prev, current in zip(words, words[1:]) if prev == current)
    repeated_phrases = 0
    for size in (2, 3):
        if len(words) < size * 2:
            continue
        for idx in range(len(words) - (size * 2) + 1):
            if words[idx:idx + size] == words[idx + size:idx + (size * 2)]:
                repeated_phrases += 1
    return repeated_words + repeated_phrases


def _timed_pauses(word_timestamps: list[dict] | None) -> list[float]:
    if not word_timestamps:
        return []
    timed_words = [
        word
        for word in word_timestamps
        if word.get("start") is not None and word.get("end") is not None
    ]
    pauses = []
    for previous, current in zip(timed_words, timed_words[1:]):
        gap = float(current["start"]) - float(previous["end"])
        if gap >= MEANINGFUL_PAUSE_SEC:
            pauses.append(gap)
    return pauses


def _speaking_duration(word_timestamps: list[dict] | None, fallback_duration: float) -> float:
    if not word_timestamps:
        return fallback_duration
    timed_words = [
        word
        for word in word_timestamps
        if word.get("start") is not None and word.get("end") is not None
    ]
    if len(timed_words) >= 2:
        return max(0.5, float(timed_words[-1]["end"]) - float(timed_words[0]["start"]))
    if len(timed_words) == 1:
        return max(0.5, float(timed_words[0]["end"]) - float(timed_words[0]["start"]))
    return fallback_duration


def _rate_fluency_score(total_words: int, audio_duration: float) -> float:
    if total_words == 0 or audio_duration <= 0:
        return 50.0
    wpm = (total_words / audio_duration) * 60
    if 45 <= wpm <= 160:
        return 100.0
    if wpm < 45:
        return max(0.0, 100.0 - ((45 - wpm) * 1.5))
    return max(0.0, 100.0 - ((wpm - 160) * 0.8))


def score_disfluency(
    transcript: str,
    audio_duration: float = 0.0,
    word_timestamps: list[dict] | None = None,
) -> dict:
    """Returns {disfluency_rate, pause_score, fluency_score}.

    This is a clinical heuristic, not a diagnostic fluency model. It combines
    transcript disfluencies, repeated words/phrases, timed pauses, and broad
    speech-rate appropriateness.
    """
    if not transcript.strip():
        return {"disfluency_rate": 0.0, "pause_score": 50.0, "fluency_score": 50.0}

    words = _normalized_words(transcript)
    total_words = len(words)
    if total_words == 0:
        return {"disfluency_rate": 0.0, "pause_score": 50.0, "fluency_score": 50.0}

    filler_count = sum(1 for word in words if word in FILLER_WORDS)
    filler_count += _count_phrase_matches(words, FILLER_PHRASES)
    repetition_count = _count_repetitions(words)
    revision_count = _count_phrase_matches(words, REVISION_MARKERS)
    disfluency_events = filler_count + repetition_count + revision_count
    disfluency_rate = round((disfluency_events / total_words) * 100, 2)

    speaking_duration = _speaking_duration(word_timestamps, audio_duration)
    pauses = _timed_pauses(word_timestamps)
    long_pause_count = sum(1 for pause in pauses if pause >= LONG_PAUSE_SEC)
    severe_pause_count = sum(1 for pause in pauses if pause >= SEVERE_PAUSE_SEC)
    pause_ratio = (sum(pauses) / speaking_duration) if speaking_duration > 0 and pauses else 0.0
    pause_score = 100.0 - (long_pause_count * 8.0) - (severe_pause_count * 7.0) - (pause_ratio * 35.0)
    pause_score = min(100.0, max(0.0, pause_score))

    event_score = max(0.0, 100.0 - (disfluency_rate * 2.5))
    rate_score = _rate_fluency_score(total_words, speaking_duration)
    fluency_score = (event_score * 0.55) + (pause_score * 0.30) + (rate_score * 0.15)
    fluency_score = max(0.0, min(100.0, fluency_score))

    return {
        "disfluency_rate": disfluency_rate,
        "pause_score": round(pause_score, 2),
        "fluency_score": round(fluency_score, 2),
    }
