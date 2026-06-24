# ML Pipeline & Scoring Engine

All ML work runs inside Celery tasks. The main entry points are:
- `server/app/tasks/analysis.py` — therapy attempt scoring
- `server/app/tasks/baseline_analysis.py` — baseline attempt scoring
- `server/app/scoring/engine.py` — final score computation
- `server/app/ml/` — individual model wrappers

---

## Models Used

| Model | File | Purpose |
|-------|------|---------|
| OpenAI Whisper | `ml/whisper_asr.py` | Speech-to-text transcription + confidence |
| HuBERT forced alignment | `ml/hubert_phoneme.py` | Phoneme-level accuracy |
| SpeechBrain | `ml/speechbrain_emotion.py` | Emotion classification (8 labels) |
| spaCy | `ml/spacy_disfluency.py` | Disfluency detection (um, uh, repetitions) |

---

## Therapy Attempt ML Pipeline

Triggered by: `POST /session/{session_id}/attempt`  
Celery task: `tasks/analysis.py::score_therapy_attempt`

```
Audio file on disk
        │
        ▼
1. Whisper ASR
   ├─ transcript (string)
   ├─ avg_confidence (0–1)
   └─ audio_duration_sec

        │
        ▼
2. HuBERT Phoneme Alignment       (only if prompt has target_phonemes)
   ├─ phoneme_accuracy (0–100)
   ├─ per_phoneme_results: { phoneme: "p", correct: true }
   └─ pa_available (bool)

        │
        ▼
3. spaCy Disfluency Scorer
   ├─ fluency_score (0–100)
   ├─ disfluency_rate (0–1)
   └─ pause_score (0–100)

        │
        ▼
4. SpeechBrain Emotion Classifier
   ├─ dominant_emotion (string: happy/sad/angry/fearful/neutral/surprised/excited/focused)
   ├─ emotion_probabilities: { label: float }
   └─ emotion_score (0–100)   ← weighted combination per age_group config

        │
        ▼
5. Derived Metrics
   ├─ speech_rate_wpm = word_count(transcript) / audio_duration_sec * 60
   ├─ speech_rate_score = score based on ideal_wpm_min/max + wpm_tolerance
   ├─ word_accuracy = len(intersection(expected_words, transcript_words))
   │                  / len(expected_words) * 100
   ├─ confidence_score = avg_confidence * 100
   ├─ rl_score = score_response_latency(response_latency_sec)
   ├─ tc_score = score_time_compression(actual_duration, target_duration_sec)
   └─ aq_score = score_answer_relevance(transcript, target_response)
                 (semantic similarity via sentence-transformers or spaCy)

        │
        ▼
6. Scoring Engine  (scoring/engine.py)
   ├─ speech_score     (see formula below)
   ├─ behavioral_score (see formula below)
   ├─ engagement_score (see formula below)
   └─ final_score      (see formula below)

        │
        ▼
7. Adaptive Decision
   └─ compare final_score against task thresholds
      (or prompt-level overrides if adaptive_threshold row exists)

        │
        ▼
8. Write to DB  (tasks/attempt_persistence.py)
   ├─ attempt_score_detail
   ├─ patient_task_progress (updated level, consecutive counts)
   └─ session_notes (queue state updated)

        │
        ▼
9. Redis Publish → WebSocket → Browser
```

---

## Scoring Formulas

All weights are stored in `task_scoring_weights`. Every task has one row.

### Speech Score
Measures the quality of the spoken output.

```
speech_score = (
    phoneme_accuracy  * speech_w_pa   +
    word_accuracy     * speech_w_wa   +
    fluency_score     * speech_w_fs   +
    speech_rate_score * speech_w_srs  +
    confidence_score  * speech_w_cs
)
```
Weights sum to 1.0. If `pa_available = false`, phoneme_accuracy weight is redistributed to other signals.

---

### Behavioral Score
Measures engagement with the task mechanics.

```
behavioral_score = (
    rl_score * behavioral_w_rl  +   ← Response Latency
    tc_score * behavioral_w_tc  +   ← Time Compression
    aq_score * behavioral_w_aq      ← Answer Relevance
)
```

**Response Latency (RL):**  
`rl_seconds` = time from mic_activated_at to speech_start_at
- ≤ 2s → 100
- 2–5s → linear decay to 60
- > 5s → further penalty

**Time Compression (TC):**  
Ratio of actual speaking duration to `prompt.target_duration_sec`
- At target → 100
- Over/under target → penalty based on deviation

**Answer Relevance (AQ):**  
Semantic similarity between `asr_transcript` and `prompt.target_response`
- Score must exceed `prompt.aq_relevance_threshold` to avoid penalty

---

### Emotion Score
Converts SpeechBrain output into an engagement-relevant signal.

```
emotion_score = sum(
    emotion_probability[label] * age_group_weight[label]
    for label in ["happy","excited","neutral","surprised","sad","angry","fearful"]
)
```
`emotion_weights_config` stores per-age-group weights. Children and adults weight emotions differently.

---

### Engagement Score
Combines emotion and behavioral signals.

```
engagement_score = (
    emotion_score    * engagement_w_emotion     +
    behavioral_score * engagement_w_behavioral
)
```

**Engagement Modifiers:**
- `engagement_score < rule_low_engagement` → apply low engagement penalty to final score
- `engagement_score > rule_high_engagement` → apply boost
- Dominant emotion = frustrated + engagement < 35% → additional penalty

---

### Final Score (Fusion)
```
final_score = (
    speech_score     * fusion_w_speech      +
    engagement_score * fusion_w_engagement
)
```
Result is clamped to [0, 100].

---

### Override Rules
Applied after computing final_score:

| Rule | Condition | Effect |
|------|-----------|--------|
| Severe PA | `phoneme_accuracy < rule_severe_pa` | Force `pass_fail = "fail"`, set `fail_reason` |
| Low confidence | `confidence_score < rule_low_confidence` | Set `low_confidence_flag = true`, set `review_recommended = true` |
| Frustrated + low engagement | `dominant_emotion = "angry"/"sad"` AND `engagement_score < 35` | Set `review_recommended = true` |

---

## Adaptive Decision Engine

Located in `tasks/session_queue.py`.

After `final_score` is computed:

```python
# Load thresholds (prompt-level override if exists, else task-level)
thresholds = prompt.adaptive_threshold or task.scoring_weights

if final_score >= thresholds.advance_to_next_level:
    decision = "advance"
elif final_score >= thresholds.stay_at_current_level_min:
    decision = "stay"
else:
    decision = "drop"
```

**Consequences per decision:**

| Decision | Action |
|----------|--------|
| `advance` | Mark prompt as passed; move to next prompt; if all prompts passed at this level → move to next difficulty level |
| `stay` | Increment attempt_number; if attempts ≥ 3 → mark prompt as failed and move on |
| `drop` | Move back to previous difficulty level; reset queue with that level's prompts; increment `adaptive_interventions` |

**Escalation trigger:**
```python
if session_notes["adaptive_interventions"] >= 2:
    # Escalate: lock plan, trigger auto-regeneration
    session_notes["escalated"] = True
    trigger plan_regeneration task
```

---

## Baseline Attempt ML Pipeline

Triggered by: `POST /baseline/{session_id}/attempt`  
Celery task: `tasks/baseline_analysis.py::score_baseline_attempt`

Slightly simpler than therapy — no behavioral scoring:

```
Audio
  ├─ Whisper ASR → transcript, duration, confidence
  ├─ HuBERT phoneme → phoneme_accuracy (if target_phoneme set)
  ├─ spaCy → fluency_score
  ├─ SpeechBrain → emotion_score
  ├─ speech_rate_wpm from transcript+duration
  └─ word_accuracy from expected_output vs transcript

Scoring formula (from baseline_item.formula_mode):
  - "auto_phoneme_only"  → weighted(phoneme_accuracy, word_accuracy)
  - "auto_simple"        → weighted(PA, WA, FS) with WPM penalty if out of range
  - default              → average of available metrics

Result stored in baseline_attempt:
  ├─ ml_phoneme_accuracy
  ├─ ml_word_accuracy
  ├─ ml_fluency_score
  ├─ ml_speech_rate_wpm + ml_speech_rate_score
  ├─ ml_confidence
  ├─ dominant_emotion + emotion_score
  ├─ engagement_score
  └─ computed_score
```

---

## ML Model Loading

Models are loaded once at worker startup (not per-request) to avoid reload overhead:

```python
# ml/whisper_asr.py
model = whisper.load_model("base")  # or "small", "medium" depending on config

# ml/hubert_phoneme.py
processor = Wav2Vec2Processor.from_pretrained("facebook/hubert-base-ls960")
model = HubertModel.from_pretrained(...)

# ml/speechbrain_emotion.py
classifier = foreign_class(source="speechbrain/emotion-recognition-wav2vec2-IEMOCAP")

# ml/spacy_disfluency.py
nlp = spacy.load("en_core_web_sm")
```

---

## Scoring Config Versioning

`task_scoring_weights` includes:
- `version` — config version string
- `approved_by` — clinician who approved these weights
- `approved_at` — timestamp

This allows tracking which clinical config was active when a score was produced, enabling future audits without recomputing old scores.
