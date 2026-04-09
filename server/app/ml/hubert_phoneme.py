import torch
import torchaudio
from functools import lru_cache
from typing import Optional
import re


_PHONEME_CHAR_ALIASES = {
    "p": ("p",),
    "b": ("b",),
    "m": ("m",),
    "t": ("t",),
    "d": ("d",),
    "n": ("n",),
    "f": ("f",),
    "v": ("v",),
    "s": ("s",),
    "z": ("z",),
    "r": ("r",),
    "l": ("l",),
    "k": ("k", "c", "q", "x"),
    "g": ("g",),
    "uː": ("u", "o"),
    "iː": ("i", "e", "y"),
    "æ": ("a",),
}


@lru_cache(maxsize=1)
def _load_model():
    bundle = torchaudio.pipelines.MMS_FA
    model = bundle.get_model()
    tokenizer = bundle.get_tokenizer()
    aligner = bundle.get_aligner()
    dictionary = bundle.get_dict()
    labels = bundle.get_labels()
    return model, bundle, tokenizer, aligner, dictionary, labels


def _normalize_text(text: str, dictionary: dict[str, int]) -> list[str]:
    if not text:
        return []
    cleaned = text.lower()
    cleaned = cleaned.replace("—", " ").replace("–", " ").replace("-", " ")
    cleaned = cleaned.replace("’", "'").replace("`", "'")
    cleaned = re.sub(r"\s+", " ", cleaned)
    words: list[str] = []
    for raw_word in cleaned.split():
        normalized = "".join(ch for ch in raw_word if ch in dictionary and ch not in {"-", "*"})
        if normalized:
            words.append(normalized)
    return words


def _target_candidates(phoneme: str, dictionary: dict[str, int]) -> set[str]:
    normalized = phoneme.strip().lower()
    normalized = normalized.replace("/", "").replace("[", "").replace("]", "")
    normalized = normalized.replace(" ", "")
    aliases = _PHONEME_CHAR_ALIASES.get(normalized)
    if aliases is None:
        aliases = tuple(ch for ch in normalized if ch.isalpha())
    return {alias for alias in aliases if alias in dictionary and alias not in {"-", "*"}}


def _is_placeholder_text(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return True
    return (
        normalized in {"n/a", "na"}
        or "picture set" in normalized
        or "target words" in normalized
        or normalized.startswith("(")
    )


def _score_target_spans(token_spans: list[tuple[str, float]], target_phonemes: list[str], dictionary: dict[str, int]) -> tuple[Optional[float], dict]:
    if not token_spans:
        return None, {}

    token_scores = [score for _, score in token_spans]
    fallback_score = round(sum(token_scores) / len(token_scores) * 100, 2)

    if not target_phonemes:
        return fallback_score, {
            "scoring_mode": "aligned_transcript",
            "matched_token_count": len(token_spans),
        }

    per_target: dict[str, dict] = {}
    matched_scores: list[float] = []

    for raw_target in target_phonemes:
        candidates = _target_candidates(raw_target, dictionary)
        target_matches = [score for token, score in token_spans if token in candidates]
        per_target[raw_target] = {
            "candidate_tokens": sorted(candidates),
            "matched_token_count": len(target_matches),
            "avg_score": round(sum(target_matches) / len(target_matches) * 100, 2) if target_matches else None,
        }
        matched_scores.extend(target_matches)

    if matched_scores:
        return round(sum(matched_scores) / len(matched_scores) * 100, 2), {
            "scoring_mode": "target_phoneme_alignment",
            "matched_token_count": len(matched_scores),
            "per_target": per_target,
        }

    return fallback_score, {
        "scoring_mode": "aligned_transcript_fallback",
        "matched_token_count": len(token_spans),
        "per_target": per_target,
    }


def align_phonemes(
    audio_path: str,
    transcript: str,
    target_phonemes: Optional[list] = None,
    reference_text: Optional[str] = None,
) -> dict:
    """Returns {phoneme_accuracy, target_phoneme_results}"""
    try:
        model, bundle, tokenizer, aligner, dictionary, labels = _load_model()
        waveform, sample_rate = torchaudio.load(audio_path)
        if sample_rate != bundle.sample_rate:
            waveform = torchaudio.functional.resample(waveform, sample_rate, bundle.sample_rate)
        with torch.inference_mode():
            emission, _ = model(waveform)
        emission_2d = emission[0] if emission.ndim == 3 else emission

        candidate_texts: list[str] = []
        for text in (
            None if _is_placeholder_text(reference_text or "") else reference_text,
            transcript,
        ):
            if text and text not in candidate_texts:
                candidate_texts.append(text)

        aligned_words: list[str] = []
        token_spans: list[tuple[str, float]] = []
        alignment_source = "transcript"
        for idx, candidate_text in enumerate(candidate_texts):
            words = _normalize_text(candidate_text, dictionary)
            if not words:
                continue
            try:
                spans_per_word = aligner(emission_2d, tokenizer(words))
            except Exception:
                continue
            aligned_words = words
            alignment_source = "reference_text" if idx == 0 and candidate_text == reference_text else "transcript"
            flat_chars = [char for word in words for char in word]
            token_spans = [
                (labels[span.token], span.score)
                for _, span in zip(flat_chars, [span for group in spans_per_word for span in group])
            ]
            break

        if not token_spans:
            return {"phoneme_accuracy": None, "target_phoneme_results": {}, "inference_ok": False}

        phoneme_accuracy, detail = _score_target_spans(token_spans, target_phonemes or [], dictionary)
        return {
            "phoneme_accuracy": phoneme_accuracy,
            "target_phoneme_results": {
                **detail,
                "alignment_source": alignment_source,
                "aligned_text": " ".join(aligned_words),
            },
            "inference_ok": phoneme_accuracy is not None,
        }
    except Exception:
        return {"phoneme_accuracy": None, "target_phoneme_results": {}, "inference_ok": False}
