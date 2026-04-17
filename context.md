# SpeechPath Codebase Analysis

## 1. What this project is

This repository implements **SpeechPath**, a speech-therapy platform with two main user roles:

- **Therapist**
- **Patient**

The product supports a full therapy loop:

1. Therapist registers and approves patients
2. Therapist assigns speech defects / problem areas to a patient
3. Patient completes a **baseline assessment**
4. Therapist generates a **weekly therapy plan**
5. Patient attempts speech prompts by recording audio
6. The backend runs **automatic speech analysis**
7. The system computes a score and an adaptive decision
8. The result is pushed back to the frontend in near real time
9. If performance is poor repeatedly, the system downgrades difficulty or escalates to therapist review

So this is not just a CRUD application. It is a **therapy workflow system** with:

- user management
- clinical content management
- baseline estimation
- ML-assisted speech scoring
- adaptive progression
- therapist oversight
- progress reporting

## 2. High-level methodology used by the project

The project uses a **hybrid methodology**:

1. **ML-based speech analysis**
2. **Rule-based scoring**
3. **Adaptive difficulty progression**
4. **Human-in-the-loop therapist escalation**

This is the core design idea of the codebase.

### Why this methodology is used

This methodology is a strong fit for speech therapy because:

- Pure ML is not reliable enough on its own for therapeutic decision-making
- Pure manual therapist review does not scale for every attempt
- Speech quality is multi-dimensional, so one metric is not enough
- Therapy needs **progressive difficulty adjustment**, not only pass/fail grading
- Distress, frustration, or unreliable ASR should trigger caution instead of blind automation

So the system combines:

- **automatic measurement** for speed and consistency
- **rules and thresholds** for safety and interpretability
- **adaptive progression logic** for learning efficiency
- **therapist review** for edge cases and repeated failures

In practice, this is a **multimodal, adaptive, human-supervised rehabilitation system**.

## 3. Actual architecture in the repository

### Frontend

- **Next.js 16**
- **React 19**
- **TypeScript**
- **Tailwind CSS 4**
- **TanStack React Query**
- **Zustand**
- **Recharts**
- **dnd-kit**

Frontend responsibilities:

- authentication UI
- therapist dashboard and patient management
- baseline assessment screens
- task/session UI
- microphone recording in browser
- live score display
- notifications
- progress charts
- drag-and-drop weekly plan editing

### Backend

- **FastAPI**
- **SQLAlchemy async**
- **PostgreSQL**
- **Celery**
- **Redis**
- **Pydantic**
- **JWT auth**

Backend responsibilities:

- REST APIs
- DB persistence
- plan generation
- baseline session handling
- therapy session handling
- adaptive engine
- progress aggregation
- WebSocket publishing through Redis

### ML / audio stack

- **OpenAI Whisper** for ASR
- **Torch / Torchaudio**
- **MMS Forced Alignment** through torchaudio for phoneme alignment
- **SpeechBrain emotion-recognition-wav2vec2-IEMOCAP**
- **spaCy** for transcript-based disfluency heuristics
- **FFmpeg** for audio conversion

## 4. Main product workflow

### 4.1 Baseline phase

The patient starts a baseline session and uploads audio for selected baseline items.

The backend:

- stores a `baseline_attempt`
- runs asynchronous ML scoring
- aggregates scored attempts into `patient_baseline_result`
- maps the average baseline score into a starting level

Current level mapping:

- `>= 75` -> `advanced`
- `>= 60 and < 75` -> `intermediate`
- `< 60` -> `beginner`

### 4.2 Plan generation phase

The weekly plan is generated from:

- patient-assigned defect IDs
- tasks mapped to those defects
- a selected or inferred baseline level

The generator tries to select tasks at the matching level, and if no tasks exist there, it falls back to `beginner`.

### 4.3 Therapy session phase

For each prompt:

1. Patient records audio in browser
2. Frontend submits the file plus microphone timestamps
3. Backend stores the attempt and audio file metadata
4. Celery runs the heavy analysis pipeline
5. Result is written to `attempt_score_detail`
6. Progress is updated
7. WebSocket message sends score back to the patient UI

### 4.4 Adaptation phase

The system does not just score; it adapts.

Current adaptive behavior includes:

- max `3` attempts per prompt
- repeated terminal failure can downgrade difficulty
- queue can be rewritten with remedial items
- after too many adaptive interventions, the session escalates to therapist review
- escalation can trigger automatic plan regeneration

Escalation limit:

- `ESCALATION_INTERVENTION_LIMIT = 2`

## 5. Scoring methodology in detail

The therapy scoring engine is a **hierarchical weighted fusion model**:

1. Compute low-level speech and behavior features
2. Combine them into intermediate scores
3. Fuse them into a final score
4. Apply clinical override rules
5. Convert final score into an adaptive decision

This is important: the code does **not** use a single end-to-end learned score. It uses **interpretable feature fusion**.

## 6. Feature extraction and formulas used

### 6.1 Word Accuracy

Implemented as a set-overlap ratio between target words and spoken words.

Formula:

```text
word_accuracy = (matched_target_words / total_target_words) * 100
```

Notes:

- punctuation is stripped
- words are lowercased
- this is **set-based**, not sequence-based
- order and repetition are ignored

Why use it:

- simple and robust for expected-response prompts
- interpretable for therapist-facing review
- inexpensive compared to semantic scoring

### 6.2 Phoneme Accuracy

The system aligns audio with transcript or reference text using torchaudio MMS forced alignment.

If target phonemes are provided, it scores only matched target phoneme spans. Otherwise it falls back to average aligned token score.

Formula:

```text
phoneme_accuracy = average(matched_alignment_scores) * 100
```

Fallback:

```text
fallback_phoneme_accuracy = average(all_aligned_token_scores) * 100
```

Why use it:

- speech therapy often targets specific sounds
- phoneme-level accuracy is more clinically useful than only word correctness

### 6.3 Speech Rate WPM

Formula:

```text
wpm = (word_count / speech_span_seconds) * 60
```

Where:

- `speech_span_seconds` comes from first-to-last timed word when available
- otherwise it falls back to audio duration
- minimum span is clamped to `0.5` seconds

### 6.4 Speech Rate Score

Therapy scoring uses a piecewise function around an ideal range.

Defaults:

- ideal min = `80`
- ideal max = `120`
- tolerance = `20`

Formula:

```text
if ideal_min <= wpm <= ideal_max:
    score = 100
elif diff <= tolerance:
    score = 100 - (diff / tolerance) * 25
elif diff <= 2 * tolerance:
    score = 75 - ((diff - tolerance) / tolerance) * 35
else:
    score = max(0, 40 - ((diff - 2 * tolerance) / (2 * tolerance)) * 40)
```

Why use it:

- ideal speaking rate matters in therapy
- but minor deviation should not be punished too harshly
- piecewise scoring is more forgiving than a hard cutoff

### 6.5 Disfluency / Fluency score

This is a **heuristic fluency model**, not a trained fluency classifier.

Detected disfluencies:

- filler words like `uh`, `um`
- filler phrases like `you know`, `kind of`
- repetitions
- revision markers like `sorry`, `actually`, `I mean`
- long and severe pauses from Whisper word timestamps

Intermediate formulas:

```text
disfluency_rate = (disfluency_events / total_words) * 100
```

```text
pause_score = 100 - (long_pause_count * 8) - (severe_pause_count * 7) - (pause_ratio * 35)
```

```text
event_score = max(0, 100 - disfluency_rate * 2.5)
```

```text
fluency_score = event_score * 0.55 + pause_score * 0.30 + rate_score * 0.15
```

Where:

- `LONG_PAUSE_SEC = 1.0`
- `SEVERE_PAUSE_SEC = 2.0`
- pauses are tracked when gap >= `0.3` seconds

Why use it:

- fluency is broader than transcript correctness
- pause behavior and self-repairs matter in speech therapy
- heuristics are transparent and easy to tune

### 6.6 Confidence score

Whisper word probabilities are averaged:

```text
confidence_score = min(100, avg_word_probability * 100)
```

Why use it:

- gives an ASR reliability signal
- helps flag cases where the transcript may be wrong

### 6.7 Response latency score (RL)

Computed from `speech_start_at - mic_activated_at`.

Discrete mapping:

- `<= 1s` -> `100`
- `<= 3s` -> `80`
- `<= 5s` -> `60`
- `> 5s` -> `40`
- missing timestamps -> `70`

Why use it:

- measures prompt responsiveness
- useful for engagement / task initiation

### 6.8 Task completion score (TC)

If target word count exists:

```text
tc_score = min(spoken_words / target_word_count, 1.0) * 100
```

Else if target duration exists:

```text
tc_score = min(duration / target_duration, 1.0) * 100
```

Else:

- default `80`

Why use it:

- distinguishes partial from complete responses
- helpful when tasks are length-based rather than exact-text based

### 6.9 Answer quality score (AQ)

Current implementation is a very simple transcript-length heuristic:

- fewer than `2` words -> `30`
- fewer than `5` words -> `60`
- otherwise -> `85`

Why use it:

- cheap placeholder estimate of response substance
- avoids zeroing out all open-ended prompts

Important note:

- this is one of the weakest heuristics in the current system
- it is more of a practical fallback than a clinically rich semantic metric

### 6.10 Emotion scoring

Emotion is first predicted by SpeechBrain. The raw model output produces:

```text
emotion_score = confidence * 100
```

Raw engagement from the emotion module is:

```text
engagement_score = emotion_score * engagement_multiplier
```

Current multipliers:

- happy -> `1.00`
- excited -> `1.00`
- surprised -> `0.85`
- neutral -> `0.60`
- sad -> `0.35`
- angry -> `0.25`
- fearful -> `0.30`

But in the therapy scoring pipeline, the final emotion contribution is recalculated again using:

- age-group clinical base scores, or
- `emotion_weights_config`

Clinical base emotion scores:

- child: happy `95`, neutral `80`, sad `50`, angry `35`
- adult: happy `85`, neutral `90`, sad `50`, angry `35`
- senior: happy `85`, neutral `90`, sad `50`, angry `35`

Clinical formula:

```text
clinical_emotion_score = base_score_for_emotion * confidence
```

If a DB emotion weight config is used:

```text
weighted_score = confidence * (weighted_capacity(dominant_emotion) / max_weighted_capacity) * 100
```

Why use it:

- the system wants emotional state to influence therapy decisions
- distress should slow progression even when speech metrics look acceptable

## 7. Core weighted scoring formulas

## 7.1 Default speech component weights

From `ScoringWeights`:

- phoneme accuracy (`speech_w_pa`) = `0.40`
- word accuracy (`speech_w_wa`) = `0.30`
- fluency score (`speech_w_fs`) = `0.15`
- speech rate score (`speech_w_srs`) = `0.10`
- confidence score (`speech_w_cs`) = `0.05`

Speech formula:

```text
speech_score =
    weighted_average([
        phoneme_accuracy * 0.40,
        word_accuracy * 0.30,
        fluency_score * 0.15,
        speech_rate_score * 0.10,
        confidence_score * 0.05
    ])
```

Important implementation detail:

- the helper renormalizes weights over only the available components
- so missing phoneme or word accuracy does not automatically zero the whole speech score

Why this weighting makes sense:

- phoneme accuracy has the highest weight because speech therapy is often articulation-focused
- word accuracy is still important for expected-response correctness
- fluency, speaking rate, and ASR confidence refine the score without dominating it

## 7.2 Behavioral weights

- response latency (`behavioral_w_rl`) = `0.40`
- task completion (`behavioral_w_tc`) = `0.35`
- answer quality (`behavioral_w_aq`) = `0.25`

Formula:

```text
behavioral_score =
    rl_score * 0.40 +
    tc_score * 0.35 +
    aq_score * 0.25
```

Why:

- quick initiation is important, but not enough by itself
- completion matters almost as much as latency
- answer quality is useful, but currently less reliable, so it gets the lowest weight

## 7.3 Engagement weights

Default weights:

- emotion contribution = `1.00`
- behavioral contribution = `0.00`

Formula:

```text
engagement_score =
    emotion_score * 1.00 +
    behavioral_score * 0.00
```

Meaning:

- in the current default configuration, engagement is effectively the emotion-based score
- behavioral score is computed but not used in engagement unless DB weights are changed

This is a very important finding from the codebase.

## 7.4 Final fusion weights

- speech contribution = `0.60`
- engagement contribution = `0.40`

Formula:

```text
final_score =
    speech_score * 0.60 +
    engagement_score * 0.40
```

Why:

- the system prioritizes speech quality over emotional state
- but engagement is still strong enough to influence progression materially

## 8. Rule-based overrides and thresholds

After the weighted score is computed, the engine applies several rule-based guards.

### 8.1 Severe phoneme cap

- threshold = `35`
- score cap = `45`

Rule:

```text
if phoneme_accuracy < 35:
    final_score = min(final_score, 45)
```

Why:

- prevents good fluency or emotion from masking severe articulation failure

### 8.2 Low engagement penalty

- threshold = `35`
- penalty = `5`

Rule:

```text
if engagement_score < 35:
    final_score -= 5
```

### 8.3 High engagement boost

- threshold = `85`
- boost = `5`

Rule:

```text
if engagement_score > 85:
    final_score += 5
```

Why:

- the engine rewards strong positive engagement and penalizes very low engagement

### 8.4 Emotion-priority override

Special override in `apply_emotion_priority_override`:

- angry or fearful with emotion score `<= 40`
- sad with emotion score `<= 55`

Effect:

- blocks `advance`
- may downgrade the performance label to `support_needed`

Why:

- emotionally distressed patients should not be pushed forward too aggressively

### 8.5 ASR review thresholds

Constants:

- low confidence review threshold = `0.55`
- no speech confidence floor = `0.35`
- no speech minimum duration = `1.0`

Review logic:

- very low ASR confidence -> review
- empty transcript -> review
- target exists and word accuracy is `0` despite a 3+ word transcript -> review

Why:

- the system recognizes that ASR can fail and explicitly exposes uncertainty

## 9. Adaptive decision logic

Base final decision:

- `>= 75` -> `advance`, pass, `advanced`
- `>= 60 and < 75` -> `stay`, pass, `satisfactory`
- `< 60` -> `drop`, fail, `needs_improvement`

Additional control logic:

- prompt-specific advance threshold can override `advance` to `stay`
- defect-specific phoneme thresholds can force a capped failing result
- non-terminal failures stay at current level until max attempts are exhausted
- session queue logic can convert final result into:
  - `stay`
  - `drop`
  - `escalated`

Why this methodology is good:

- it separates **performance scoring** from **session management**
- a low score does not always immediately drop the patient if retry is still appropriate

## 10. Baseline methodology

Baseline scoring is intentionally simpler than therapy scoring.

Two main formula modes are implemented:

### 10.1 `auto_phoneme_only`

Default weights:

- phoneme accuracy = `0.80`
- word accuracy = `0.20`

Formula:

```text
baseline_score = weighted_average(pa * 0.80, wa * 0.20)
```

Why:

- suitable for articulation-heavy diagnostic items

### 10.2 `auto_simple`

Default weights:

- phoneme accuracy = `0.50`
- word accuracy = `0.30`
- fluency score = `0.20`

Formula:

```text
baseline_score = weighted_average(pa * 0.50, wa * 0.30, fs * 0.20)
```

If WPM is outside configured range:

```text
baseline_score = max(0, baseline_score - 10)
```

Why:

- gives a broader initial estimate than phoneme-only scoring
- still stays simpler than the therapy engine

### 10.3 Baseline aggregation

The completed baseline result is the mean of scored baseline attempts:

```text
avg_score = mean(computed_score_per_attempt)
raw_score = round(avg_score)
severity = level_from_score(avg_score)
```

Polling currently treats baseline pass/fail as:

- `computed_score >= 70` -> pass
- otherwise fail

## 11. Why this overall methodology is appropriate

The codebase is built around a sensible rehabilitation idea:

- **baseline** estimates the patient starting point
- **weekly plans** turn that into structured daily practice
- **attempt-level ML scoring** provides immediate feedback
- **weighted fusion** keeps the score explainable
- **adaptive queue logic** prevents repeated failure loops
- **therapist escalation** keeps the clinician in control when automation is insufficient

This is better than a single black-box model because:

- scores are explainable
- thresholds are tunable
- clinicians can audit why a decision happened
- different task types can reuse the framework with different DB weights

## 12. Important implementation observations and gaps

This section matters because the repository contains both a good design and some implementation inconsistencies.

### 12.1 Adaptive thresholds exist in DB, but core decision still uses hardcoded `75/60`

The `ScoringWeights` model loads:

- `adaptive_advance_threshold`
- `adaptive_stay_min`
- `adaptive_stay_max`
- `adaptive_drop_threshold`

But `score_attempt()` currently classifies decisions using fixed constants:

- `75`
- `60`

So DB thresholds are only partially respected.

### 12.2 Engagement defaults make behavioral engagement unused

Default configuration:

- `engagement_w_emotion = 1.00`
- `engagement_w_behavioral = 0.00`

So behavioral score is calculated, but by default it does not affect engagement at all.

### 12.3 AQ score is still simplistic

`compute_aq_score()` is just a response-length heuristic, not semantic relevance scoring.

### 12.4 Word accuracy is set-based

This is fast and interpretable, but it ignores:

- order
- repeated mistakes
- substitutions
- partial phrase structure

### 12.5 Baseline result currently collapses multiple scored items into one average

That is practical, but it is a coarse summary and may hide per-domain differences.

### 12.6 Plan regeneration contains at least one suspicious incomplete block

In `plan_regeneration.py`, the "archive current approved plan" section sets:

```text
archived = 0
```

without actually performing the archive query shown in the design intent.

So that part looks incomplete or only partially implemented.

## 13. Tech stack summary

### Frontend stack

- Next.js 16
- React 19
- TypeScript 5
- Tailwind CSS 4
- TanStack React Query
- Zustand
- Recharts
- dnd-kit
- Sonner

### Backend stack

- FastAPI
- SQLAlchemy 2 async
- PostgreSQL
- Pydantic 2
- Celery 5
- Redis 5
- Uvicorn
- JWT auth with `python-jose`

### ML / audio stack

- openai-whisper
- torch
- torchaudio
- speechbrain
- transformers
- spaCy
- soundfile
- aiofiles
- FFmpeg

## 14. Final conclusion

SpeechPath is a **multimodal adaptive speech-therapy platform** rather than a generic learning app.

Its core methodology is:

- baseline-driven entry level selection
- ML-assisted speech analysis
- weighted interpretable scoring
- rule-based clinical safeguards
- adaptive task progression
- therapist escalation when automation should stop

The methodology is well chosen because it balances:

- automation
- explainability
- safety
- clinical practicality

The most important formulas in the codebase are the weighted fusion formulas for:

- speech score
- behavioral score
- engagement score
- final score

with the key default fusion values:

- speech: `60%`
- engagement: `40%`
- phoneme accuracy inside speech: `40%`
- word accuracy inside speech: `30%`

Overall, this is a strong architecture for an academic or final-year project because it shows:

- full-stack engineering
- applied ML integration
- asynchronous system design
- adaptive learning logic
- domain-specific scoring methodology
- real-time feedback and progress tracking
