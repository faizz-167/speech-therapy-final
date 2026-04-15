# Metric Calculation Changes

This document summarizes the scoring and metric calculation changes made for emotion detection, emotion scoring, fluency scoring, speech-rate scoring, and related metric delivery.

## 1. Emotion Detection

### Previous behavior

- The system attempted to classify emotion using SpeechBrain, but the runtime path often failed and returned the fallback:

```text
dominant_emotion = None
emotion_score = 0.0
engagement_score = 0.0
```

- The UI therefore displayed `Waiting for emotion` or `0.0%`.

### Changes made

File:

- `server/app/ml/speechbrain_emotion.py`

Implemented the same model loading path used by `Emotion_analysis.ipynb`:

```python
foreign_class(
    source="speechbrain/emotion-recognition-wav2vec2-IEMOCAP",
    pymodule_file="custom_interface.py",
    classname="CustomEncoderWav2vec2Classifier",
)
```

The model now returns:

- `dominant_emotion`
- `emotion_score`
- `engagement_score`
- `confidence`
- `raw_label`
- `emotion_probabilities`

Supported model labels:

| Raw label | Display emotion |
|---|---|
| `hap` | `happy` |
| `sad` | `sad` |
| `ang` | `angry` |
| `neu` | `neutral` |

### Runtime fixes added

The emotion model also needed several runtime fixes:

- `huggingface-hub<1.0` because SpeechBrain 1.0.2 still uses `use_auth_token`.
- `transformers==4.46.3` because newer Transformers requires Torch 2.6+ for some checkpoint loading paths.
- `soundfile==0.12.1`.
- SpeechBrain fetches are forced to copy files instead of creating Windows symlinks.
- Broken local proxy values such as `127.0.0.1:9` are cleared before model loading.
- Browser `.webm` recordings are converted to 16 kHz mono WAV using `ffmpeg` before classification.

Dependencies updated in:

- `server/requirements.txt`

Local model/cache folders ignored in:

- `server/.gitignore`

## 2. Emotion Score Thresholds

### Previous behavior

The model could correctly detect an emotion, but the final emotion score could still become `0.0`.

Reason:

- `emotion_weights_config` had `w_angry = 0.00`.
- The scoring formula normalized by configured emotion weights.
- Therefore, any `angry` prediction produced:

```text
emotion_score = confidence * 0 = 0.0
```

### Changes made

File:

- `server/app/tasks/analysis.py`

Added clinical base scores for the four supported emotions.

| Age group | Happy | Neutral | Sad | Angry |
|---|---:|---:|---:|---:|
| child | 95 | 80 | 50 | 35 |
| adult | 85 | 90 | 50 | 35 |
| senior | 85 | 90 | 50 | 35 |

Final emotion score is now confidence-scaled:

```text
emotion_score = clinical_base_score * model_confidence
```

Examples:

```text
child + angry + confidence 1.0 = 35.0
adult + neutral + confidence 1.0 = 90.0
child + sad + confidence 0.8 = 40.0
```

### Seed data updated

File:

- `server/seed_data.py`

Updated `EMOTION_WEIGHTS` to version `2`:

| Age group | Happy | Excited | Neutral | Surprised | Sad | Angry | Fearful |
|---|---:|---:|---:|---:|---:|---:|---:|
| child | 0.95 | 0.90 | 0.80 | 0.75 | 0.50 | 0.35 | 0.35 |
| adult | 0.85 | 0.80 | 0.90 | 0.75 | 0.50 | 0.35 | 0.35 |

The seeder now updates existing `emotion_weights_config` rows instead of leaving old zero values unchanged.

The existing database rows were also updated to:

```text
child: w_happy=0.95, w_neutral=0.80, w_sad=0.50, w_angry=0.35, version=2
adult: w_happy=0.85, w_neutral=0.90, w_sad=0.50, w_angry=0.35, version=2
```

## 3. Emotion Display

File:

- `client/components/patient/ScoreDisplay.tsx`

Added a visible emotion panel:

- `Detected Emotion`
- `Emotion Score`

The metric grid also displays:

- `Emotion Score`
- `Engagement`
- `Dominant Emotion`

## 4. Emotion Score Delivery

File:

- `server/app/tasks/analysis.py`

The WebSocket `score_ready` payload now includes:

```text
emotion_score
```

This ensures the patient score screen receives the emotion score immediately from live scoring, not only from polling.

## 5. Fluency Score

### Previous behavior

File:

- `server/app/ml/spacy_disfluency.py`

The previous fluency score only counted a few filler words:

```python
FILLER_WORDS = {"uh", "um", "er", "ah", "like", "you know", "sort of", "kind of"}
fluency_score = 100 - (disfluency_rate * 2)
```

If the transcript had no filler words, the score became:

```text
fluency_score = 100.0
```

This meant repetitions, pauses, restarts, and speech blocks were not properly reflected.

### New fluency calculation

File:

- `server/app/ml/spacy_disfluency.py`

The fluency calculation now checks:

- filler words: `uh`, `um`, `er`, `ah`, `eh`, `hmm`, `like`
- filler phrases: `you know`, `sort of`, `kind of`
- repeated words: for example `I I`, `stop stop`
- repeated phrases
- repair/revision markers: `I mean`, `sorry`, `wait`, `actually`, `no I mean`
- meaningful pauses from Whisper word timestamps
- broad speech-rate appropriateness

New fluency formula:

```text
fluency_score =
    55% disfluency-event score
  + 30% pause score
  + 15% broad rate fluency score
```

Pause thresholds:

| Pause type | Threshold |
|---|---:|
| meaningful pause | 0.3 sec |
| long pause | 1.0 sec |
| severe pause | 2.0 sec |

Returned values remain:

```text
disfluency_rate
pause_score
fluency_score
```

### Fluency verification examples

Clean sample:

```text
transcript: "I want to stop this now"
result: high fluency
```

Repeated/filler sample:

```text
transcript: "I I want to stop stop this um now"
result: lower fluency
```

Observed test output:

```text
clean  -> fluency_score around 93.8
repeat -> fluency_score around 48.2
```

## 6. Speech Rate WPM

### Previous behavior

Speech rate was calculated from:

```text
word_count / total_duration * 60
```

Problem:

- Total duration can include pre-speech waiting time.
- Response delay is already measured separately.
- This could make WPM artificially low.

### New behavior

Files:

- `server/app/tasks/analysis.py`
- `server/app/tasks/baseline_analysis.py`

Speech rate now uses Whisper word timestamps when available:

```text
speech_span = last_word_end - first_word_start
wpm = word_count / speech_span * 60
```

Fallback:

```text
if word timestamps are unavailable, use total ASR duration
```

This makes WPM closer to actual speaking speed rather than total recording time.

## 7. Speech Rate Score

### Previous behavior

The previous speech-rate score used a simple linear penalty:

```python
if ideal_min <= wpm <= ideal_max:
    return 100
else:
    return 100 - (difference / tolerance) * 30
```

### New behavior

Files:

- `server/app/tasks/analysis.py`
- `server/app/tasks/baseline_analysis.py`

Speech-rate score now uses a bounded clinical curve:

| WPM location | Score behavior |
|---|---|
| inside ideal range | 100 |
| within 1 tolerance outside range | decreases from 100 to 75 |
| within 2 tolerances outside range | decreases from 75 to 40 |
| beyond 2 tolerances | decreases from 40 to 0 |

Example with ideal range `80-120` and tolerance `20`:

| WPM | Speech-rate score |
|---:|---:|
| 40 | 40 |
| 60 | 75 |
| 80 | 100 |
| 100 | 100 |
| 120 | 100 |
| 140 | 75 |
| 160 | 40 |
| 200 | 0 |

Important distinction:

- `Speech Rate (WPM)` is raw speed and can be above 100.
- `Speech Rate Score` is normalized and capped at 100.

## 8. Baseline Metric Alignment

File:

- `server/app/tasks/baseline_analysis.py`

Baseline attempts now use:

- the improved fluency calculation
- Whisper word timestamps for WPM
- the new speech-rate score curve
- item-level `wpm_range` when available

Before this, baseline speech-rate score always used default `80-120` WPM.

## 9. Confidence Score

File:

- `server/app/ml/whisper_asr.py`

No major formula change was made to confidence.

Confidence is calculated from Whisper word-level probabilities:

```text
avg_confidence = sum(word probabilities) / number of words
confidence_score = avg_confidence * 100
```

Meaning:

- This is ASR confidence.
- It is not patient confidence.
- It estimates how confident Whisper is in the transcript.

Review threshold:

```text
avg_confidence < 0.55 -> review recommended
```

## 10. Final Score Relationship

File:

- `server/app/scoring/engine.py`

The final scoring formula still uses:

```text
Speech Score =
    PA * speech_w_pa
  + WA * speech_w_wa
  + Fluency * speech_w_fs
  + Speech Rate Score * speech_w_srs
  + Confidence * speech_w_cs

Engagement Score =
    Emotion Score * engagement_w_emotion
  + Behavioral Score * engagement_w_behavioral

Final Score =
    Speech Score * fusion_w_speech
  + Engagement Score * fusion_w_engagement
```

The main improvement is that the input metrics are now less misleading:

- angry/sad emotion no longer becomes zero
- fluency no longer becomes automatic 100
- speech rate uses actual speech span
- speech-rate score uses a bounded clinical curve

## 11. Verification Performed

Python syntax checks passed for:

- `server/app/ml/speechbrain_emotion.py`
- `server/app/ml/spacy_disfluency.py`
- `server/app/tasks/analysis.py`
- `server/app/tasks/baseline_analysis.py`
- `server/seed_data.py`

Direct emotion model verification returned:

```text
dominant_emotion: happy
emotion_score: 100.0
confidence: 1.0
emotion_probabilities:
  hap: 1.0
  neu: near 0
  ang: near 0
  sad: near 0
```

Direct clinical emotion score verification:

```text
child happy   -> 95.0
child neutral -> 80.0
child sad     -> 50.0
child angry   -> 35.0
adult happy   -> 85.0
adult neutral -> 90.0
adult sad     -> 50.0
adult angry   -> 35.0
```

Direct speech-rate score verification:

```text
40 WPM  -> 40.0
60 WPM  -> 75.0
80 WPM  -> 100.0
120 WPM -> 100.0
140 WPM -> 75.0
160 WPM -> 40.0
200 WPM -> 0.0
```

## 12. Runtime Notes

After these changes:

1. Restart FastAPI.
2. Restart the Celery worker.
3. Run a new attempt.

Existing attempts keep their stored old scores. New scoring logic applies only to new attempts unless old attempts are reprocessed.

