# Database Design

**Database:** PostgreSQL (hosted on Neon)  
**ORM:** SQLAlchemy 2.0 (async)  
**Models location:** `server/app/models/`

---

## Entity-Relationship Overview

```
therapist ──────────────────────────────────── patient
    │                                              │
    │  (assigned_therapist_id)                     │
    │                                              │
    ├── therapy_plan ◄─────────────────────────────┤
    │       │                                      │
    │       ├── plan_task_assignment               │
    │       │       │                              │
    │       │       └── task ──── task_level ──── prompt
    │       │                         │               │
    │       │                    task_defect_mapping  │
    │       │                         │               │
    │       └── plan_revision_history defect          │
    │                                 │               │
    ├── session ─────────────────────────────────────┤
    │       │                                         │
    │       └── session_prompt_attempt               │
    │               │                                 │
    │               └── attempt_score_detail          │
    │                                                 │
    │── baseline_assessment                           │
    │       │                                         │
    │       ├── baseline_section                      │
    │       │       └── baseline_item                 │
    │       │                                         │
    │       └── patient_baseline_result ─────────────┤
    │               └── baseline_item_result          │
    │                                                 │
    └── therapist_notification          patient_notification
                                        patient_task_progress
                                        session_emotion_summary
```

---

## Tables

### `therapist`
Stores registered therapist accounts.

| Column | Type | Notes |
|--------|------|-------|
| `therapist_id` | UUID (PK) | Auto-generated |
| `therapist_code` | String (unique) | 8-char code patients use to register |
| `full_name` | String | Required |
| `email` | String (unique) | Login credential |
| `password_hash` | String | bcrypt hash |
| `license_number` | String | Optional |
| `specialization` | String | Optional |
| `years_of_experience` | Integer | Optional |
| `role` | String | Always `"therapist"` |

---

### `patient`
Stores patient accounts. Requires therapist approval to become active.

| Column | Type | Notes |
|--------|------|-------|
| `patient_id` | UUID (PK) | |
| `email` | String (unique) | Login credential |
| `password_hash` | String | bcrypt hash |
| `full_name` | String | |
| `date_of_birth` | Date | |
| `gender` | String | |
| `status` | String | `pending` → `approved` |
| `primary_diagnosis` | String | Set by therapist on approval |
| `clinical_notes` | Text | Set by therapist |
| `assigned_therapist_id` | UUID (FK → therapist) | |
| `pre_assigned_defect_ids` | JSONB | `{defect_ids: ["d1","d2"]}` |
| `current_streak` | Integer | Consecutive active days |
| `longest_streak` | Integer | Best historical streak |
| `role` | String | Always `"patient"` |

---

### `defect`
Clinical speech defect categories (seeded from clinical data).

| Column | Type | Notes |
|--------|------|-------|
| `defect_id` | String (PK) | e.g., `"DEF001"` |
| `code` | String (unique) | Short code |
| `name` | String | Human-readable name |
| `category` | String | Grouping |
| `age_group` | String | Target age group |
| `description` | Text | Clinical description |

---

### `task`
Individual therapy exercises. Each task has multiple difficulty levels.

| Column | Type | Notes |
|--------|------|-------|
| `task_id` | String (PK) | |
| `name` | String | |
| `type` | String | Exercise category |
| `task_mode` | String | Interaction mode |
| `description` | Text | |
| `ideal_wpm_min` | Float | Target speech rate lower bound |
| `ideal_wpm_max` | Float | Target speech rate upper bound |
| `wpm_tolerance` | Float | Allowed deviation from target |
| `source_id` | String | Reference to original data source |

---

### `task_level`
Difficulty tiers for a task (beginner / intermediate / advanced).

| Column | Type | Notes |
|--------|------|-------|
| `level_id` | String (PK) | |
| `task_id` | String (FK → task) | |
| `level_name` | String | `beginner`, `intermediate`, `advanced` |
| `difficulty_score` | Integer | Numeric rank |
| `source_level_id` | String | Reference |

---

### `prompt`
Individual exercise stimuli within a task level. One attempt = one prompt.

| Column | Type | Notes |
|--------|------|-------|
| `prompt_id` | String (PK) | |
| `level_id` | String (FK → task_level) | |
| `prompt_type` | String | Visual, audio, text |
| `task_mode` | String | |
| `scenario_context` | Text | Contextual framing |
| `instruction` | Text | Shown to patient |
| `display_content` | Text | Word/image/sentence displayed |
| `target_response` | Text | Expected spoken output |
| `accuracy_check` | String | Scoring method |
| `evaluation_criteria` | Text | |
| `speech_target` | JSONB | Target phonemes & words |
| `eval_scope` | String | What to evaluate (word, sentence, etc.) |
| `target_phonemes` | JSONB | List of target phonemes |
| `pass_message` | Text | Shown on pass |
| `partial_message` | Text | Shown on partial |
| `fail_message` | Text | Shown on fail |
| `active` | Boolean | Whether prompt is enabled |
| `tc_mode` | String | Time Compression evaluation mode |
| `target_word_count` | Integer | |
| `target_duration_sec` | Float | Expected speaking duration |
| `min_length_words` | Integer | Minimum acceptable response length |
| `aq_relevance_threshold` | Float | Minimum answer relevance score |

---

### `adaptive_threshold`
Per-prompt overrides for scoring thresholds (optional; falls back to task-level thresholds).

| Column | Type | Notes |
|--------|------|-------|
| `threshold_id` | String (PK) | |
| `prompt_id` | String (FK → prompt, unique) | |
| `advance_to_next_level` | Float | Score ≥ this → advance |
| `stay_at_current_level_min` | Float | Score in [min, max] → stay |
| `stay_at_current_level_max` | Float | |

---

### `task_scoring_weights`
Scoring configuration per task. Controls how each signal contributes to the final score.

| Column | Type | Notes |
|--------|------|-------|
| `weight_id` | String (PK) | |
| `task_id` | String (FK → task, unique) | One row per task |
| `speech_w_pa` | Float | Weight: Phoneme Accuracy |
| `speech_w_wa` | Float | Weight: Word Accuracy |
| `speech_w_fs` | Float | Weight: Fluency Score |
| `speech_w_srs` | Float | Weight: Speech Rate Score |
| `speech_w_cs` | Float | Weight: Confidence Score |
| `fusion_w_speech` | Float | Weight: speech component in final score |
| `fusion_w_engagement` | Float | Weight: engagement component in final score |
| `engagement_w_emotion` | Float | Weight: emotion in engagement |
| `engagement_w_behavioral` | Float | Weight: behavioral in engagement |
| `behavioral_w_rl` | Float | Weight: Response Latency |
| `behavioral_w_tc` | Float | Weight: Time Compression |
| `behavioral_w_aq` | Float | Weight: Answer Relevance |
| `adaptive_advance_threshold` | Float | Default advance threshold |
| `adaptive_stay_min` | Float | |
| `adaptive_stay_max` | Float | |
| `adaptive_drop_threshold` | Float | Score < this → drop level |
| `rule_severe_pa` | Float | PA below this = override to fail |
| `rule_low_engagement` | Float | Engagement below this = penalty |
| `rule_high_engagement` | Float | Engagement above this = boost |
| `rule_low_confidence` | Float | Confidence below this = review flag |
| `version` | String | Config version |
| `approved_by` | String | Clinician who approved |
| `approved_at` | DateTime | |

---

### `task_defect_mapping`
Which tasks address which defects (many-to-many).

| Column | Type | Notes |
|--------|------|-------|
| `mapping_id` | String (PK) | |
| `task_id` | String (FK → task) | |
| `defect_id` | String (FK → defect) | |
| `relevance_level` | String | `primary`, `secondary` |
| `clinical_notes` | Text | |
| UNIQUE | (task_id, defect_id) | |

---

### `defect_pa_threshold`
Per-defect minimum phoneme accuracy thresholds.

| Column | Type | Notes |
|--------|------|-------|
| `threshold_id` | String (PK) | |
| `defect_id` | String (FK → defect) | |
| `min_pa_to_pass` | Float | Minimum PA score to pass (0–100) |
| `target_phonemes` | ARRAY | Specific phonemes to evaluate |
| `phoneme_scope` | String | `all`, `specific` |
| `severity_modifier` | Float | Adjusts threshold by severity |
| `notes` | Text | |

---

### `emotion_weights_config`
Per-age-group weights for emotion classification output.

| Column | Type | Notes |
|--------|------|-------|
| `config_id` | String (PK) | |
| `age_group` | String (unique) | `child`, `adult` |
| `w_happy` | Float | Weight for "happy" emotion |
| `w_excited` | Float | |
| `w_neutral` | Float | |
| `w_surprised` | Float | |
| `w_sad` | Float | |
| `w_angry` | Float | |
| `w_fearful` | Float | |
| `w_positive_affect` | Float | |
| `w_focused` | Float | |
| `version` | String | |
| `approved_by` | String | |
| `approved_at` | DateTime | |

---

### `therapy_plan`
A weekly treatment plan for a patient.

| Column | Type | Notes |
|--------|------|-------|
| `plan_id` | UUID (PK) | |
| `patient_id` | UUID (FK → patient) | |
| `therapist_id` | UUID (FK → therapist) | |
| `plan_name` | String | |
| `goals` | Text | Clinical goals |
| `start_date` | Date | |
| `end_date` | Date | |
| `status` | String | `draft` → `approved` → `archived` |
| `created_at` | DateTime | |

---

### `plan_task_assignment`
Links a task to a specific day and priority slot in a plan.

| Column | Type | Notes |
|--------|------|-------|
| `assignment_id` | UUID (PK) | |
| `plan_id` | UUID (FK → therapy_plan) | |
| `task_id` | String (FK → task) | |
| `therapist_id` | UUID (FK → therapist) | |
| `day_index` | Integer | 0 = Monday … 6 = Sunday |
| `priority_order` | Integer | Task order within a day |
| `status` | String | `pending`, `completed` |
| `paused` | Boolean | Paused by escalation |
| `clinical_rationale` | Text | Why this task was chosen |
| `initial_level_name` | String | Starting difficulty |
| UNIQUE | (plan_id, day_index, priority_order) | |

---

### `plan_revision_history`
Audit trail of all plan modifications.

| Column | Type | Notes |
|--------|------|-------|
| `revision_id` | UUID (PK) | |
| `plan_id` | UUID (FK → therapy_plan) | |
| `therapist_id` | UUID (FK → therapist) | |
| `action` | String | `update_level`, `add_task`, `remove_task`, `reorder`, `auto_regenerated_after_escalation` |
| `assignment_id` | UUID (FK, nullable) | Which assignment was changed |
| `old_value` | JSONB | Before state |
| `new_value` | JSONB | After state |
| `note` | Text | Human note |
| `created_at` | DateTime | |

---

### `baseline_assessment`
A standardized clinical assessment instrument (e.g., an articulation test).

| Column | Type | Notes |
|--------|------|-------|
| `baseline_id` | String (PK) | |
| `code` | String (unique) | |
| `name` | String | Assessment name |
| `domain` | String | Speech domain (articulation, fluency, etc.) |
| `description` | Text | |
| `administration_method` | String | |

---

### `baseline_section`
Grouping of baseline items within an assessment.

| Column | Type | Notes |
|--------|------|-------|
| `section_id` | String (PK) | |
| `baseline_id` | String (FK → baseline_assessment) | |
| `section_name` | String | |
| `instructions` | Text | |
| `order_index` | Integer | Display order |
| `target_defect_id` | String (FK → defect, nullable) | |

---

### `baseline_item`
A single test item inside a baseline section.

| Column | Type | Notes |
|--------|------|-------|
| `item_id` | String (PK) | |
| `section_id` | String (FK → baseline_section) | |
| `task_name` | String | |
| `instruction` | Text | Shown to patient |
| `display_content` | Text | |
| `expected_output` | Text | Target speech output |
| `target_phoneme` | String | Phoneme being tested |
| `response_type` | String | `word`, `sentence`, `paragraph` |
| `formula_mode` | String | Scoring formula to apply |
| `formula_weights` | JSONB | Per-metric weights |
| `fusion_weights` | JSONB | Speech vs engagement weights |
| `wpm_range` | JSONB | `{min, max}` target words per minute |
| `defect_codes` | ARRAY | Related defects |
| `max_score` | Float | Maximum achievable score |
| `image_keyword` | String | Image to display (if any) |
| `reference_text` | Text | For comparison scoring |
| `scope` | String | Evaluation scope |
| `scoring_method` | String | |
| `order_index` | Integer | |

---

### `baseline_defect_mapping`
Maps a baseline assessment to the defects it evaluates.

| Column | Type | Notes |
|--------|------|-------|
| `mapping_id` | String (PK) | |
| `baseline_id` | String (FK) | |
| `defect_id` | String (FK) | |
| `relevance_level` | String | |
| `clinical_notes` | Text | |
| UNIQUE | (baseline_id, defect_id) | |

---

### `patient_baseline_result`
Aggregated result after a patient completes a baseline assessment.

| Column | Type | Notes |
|--------|------|-------|
| `result_id` | UUID (PK) | |
| `patient_id` | UUID (FK → patient) | |
| `baseline_id` | String (FK → baseline_assessment) | |
| `therapist_id` | UUID (FK → therapist) | |
| `session_id` | UUID (FK → session, nullable) | Linked baseline session |
| `assessed_on` | Date | |
| `raw_score` | Float | Overall score |
| `percentile` | Float | |
| `severity_rating` | String | `mild`, `moderate`, `severe` |
| `notes` | Text | |

---

### `baseline_item_result`
Score for a single item within a baseline result.

| Column | Type | Notes |
|--------|------|-------|
| `item_result_id` | UUID (PK) | |
| `result_id` | UUID (FK → patient_baseline_result) | |
| `item_id` | String (FK → baseline_item) | |
| `score_given` | Float | Score for this item |
| `error_noted` | String | Error description |
| `clinician_note` | Text | |

---

### `baseline_attempt`
Raw ML output for each audio submission during baseline.

| Column | Type | Notes |
|--------|------|-------|
| `attempt_id` | UUID (PK) | |
| `session_id` | UUID (FK → session) | |
| `item_id` | String (FK → baseline_item) | |
| `audio_file_path` | String | |
| `result` | String | `pending`, `scored`, `failed` |
| `ml_phoneme_accuracy` | Float | 0–100 |
| `ml_word_accuracy` | Float | 0–100 |
| `ml_fluency_score` | Float | 0–100 |
| `ml_speech_rate_wpm` | Integer | Words per minute |
| `ml_speech_rate_score` | Float | 0–100 |
| `ml_confidence` | Float | Whisper confidence 0–1 |
| `dominant_emotion` | String | Detected emotion |
| `emotion_score` | Float | 0–100 |
| `engagement_score` | Float | 0–100 |
| `pa_available` | Boolean | Whether phoneme alignment succeeded |
| `asr_transcript` | Text | Whisper transcript |
| `computed_score` | Float | Final baseline score |
| `created_at` | DateTime | |

---

### `session`
A therapy or baseline session.

| Column | Type | Notes |
|--------|------|-------|
| `session_id` | UUID (PK) | |
| `plan_id` | UUID (FK → therapy_plan, nullable) | |
| `patient_id` | UUID (FK → patient) | |
| `therapist_id` | UUID (FK → therapist, nullable) | |
| `session_date` | DateTime | |
| `duration_minutes` | Float | |
| `session_type` | String | `therapy`, `baseline` |
| `session_notes` | Text | JSON-serialized adaptive state (see below) |

**session_notes JSON schema:**
```json
{
  "assignment_id": "uuid",
  "task_id": "string",
  "queue_items": ["prompt_id1", "prompt_id2"],
  "current_queue_level": "beginner",
  "attempted_prompt_ids": [],
  "passed_prompt_ids": [],
  "adaptive_interventions": 0,
  "escalated": false,
  "adaptation_history": [],
  "completed": false,
  "completion_status": null
}
```

---

### `session_prompt_attempt`
One audio submission by a patient for a specific prompt.

| Column | Type | Notes |
|--------|------|-------|
| `attempt_id` | UUID (PK) | |
| `session_id` | UUID (FK → session) | |
| `prompt_id` | String (FK → prompt) | |
| `attempt_number` | Integer | 1, 2, or 3 (max 3 per prompt) |
| `result` | String | `pending`, `scored`, `failed` |
| `accuracy_score` | Float | Final score (0–100) |
| `asr_transcript` | Text | |
| `audio_file_path` | String | |
| `task_mode` | String | |
| `prompt_type` | String | |
| `speech_detected` | Boolean | |
| `response_latency_sec` | Float | Time from mic open to speech start |
| `therapist_override_note` | Text | |
| `mic_activated_at` | DateTime | |
| `speech_start_at` | DateTime | |
| `created_at` | DateTime | |

---

### `attempt_score_detail`
Detailed ML scoring breakdown for a therapy attempt. One row per attempt.

| Column | Type | Notes |
|--------|------|-------|
| `detail_id` | UUID (PK) | |
| `attempt_id` | UUID (FK → session_prompt_attempt, unique) | |
| `word_accuracy` | Float | 0–100 |
| `phoneme_accuracy` | Float | 0–100 |
| `pa_available` | Boolean | |
| `fluency_score` | Float | 0–100 |
| `disfluency_rate` | Float | |
| `pause_score` | Float | |
| `speech_rate_wpm` | Integer | |
| `speech_rate_score` | Float | 0–100 |
| `confidence_score` | Float | 0–100 |
| `rl_score` | Float | Response Latency score |
| `rl_seconds` | Float | Raw latency |
| `tc_score` | Float | Time Compression score |
| `aq_score` | Float | Answer Relevance score |
| `behavioral_score` | Float | 0–100 |
| `dominant_emotion` | String | |
| `emotion_score` | Float | 0–100 |
| `engagement_score` | Float | 0–100 |
| `speech_score` | Float | 0–100 |
| `final_score` | Float | Fused speech + engagement (0–100) |
| `adaptive_decision` | String | `advance`, `stay`, `drop` |
| `pass_fail` | String | `pass`, `fail` |
| `fail_reason` | String | |
| `performance_level` | String | |
| `baseline_score_ref` | Float | Patient's baseline for this task |
| `progress_delta` | Float | Improvement vs baseline |
| `progress_classification` | String | `improved`, `regressed`, `stable` |
| `low_confidence_flag` | Boolean | |
| `review_recommended` | Boolean | |
| `warmup_gate_passed` | Boolean | |
| `target_phoneme_results` | JSONB | Per-phoneme pass/fail |
| `asr_transcript` | Text | |
| `audio_duration_sec` | Float | |
| `created_at` | DateTime | |

---

### `patient_task_progress`
Per-patient, per-task progress tracking for the adaptive engine.

| Column | Type | Notes |
|--------|------|-------|
| `progress_id` | UUID (PK) | |
| `patient_id` | UUID (FK → patient) | |
| `task_id` | String (FK → task) | |
| `current_level_id` | String (FK → task_level) | Current difficulty |
| `consecutive_passes` | Integer | For auto-advance logic |
| `consecutive_fails` | Integer | For auto-drop logic |
| `overall_accuracy` | Float | Running average |
| `last_final_score` | Float | Most recent score |
| `baseline_score` | Float | First score (reference) |
| `total_attempts` | Integer | |
| `sessions_at_level` | Integer | Sessions at current level |
| `level_locked_until` | DateTime (nullable) | Prevents drop during lockout |
| `last_attempted_at` | DateTime | |
| UNIQUE | (patient_id, task_id) | |

---

### `session_emotion_summary`
Aggregated emotion data per session for analytics.

| Column | Type | Notes |
|--------|------|-------|
| `summary_id` | UUID (PK) | |
| `session_id` | UUID (FK → session) | |
| `patient_id` | UUID (FK → patient) | |
| `session_date` | DateTime | |
| `dominant_emotion` | String | Most common emotion this session |
| `avg_frustration` | Float | |
| `avg_engagement` | Float | |
| `drop_count` | Integer | How many level drops occurred |

---

### `audio_file`
Tracks uploaded audio files. Can be purged after scoring.

| Column | Type | Notes |
|--------|------|-------|
| `file_id` | UUID (PK) | |
| `attempt_id` | UUID (FK, nullable) | |
| `patient_id` | UUID (FK → patient) | |
| `session_id` | UUID (FK → session) | |
| `file_path` | String | Server file path |
| `file_size_bytes` | Integer | |
| `duration_sec` | Float | |
| `mime_type` | String | |
| `created_at` | DateTime | |
| `purged_at` | DateTime (nullable) | Set when file is deleted |

---

### `therapist_notification`

| Column | Type | Notes |
|--------|------|-------|
| `notification_id` | UUID (PK) | |
| `therapist_id` | UUID (FK) | |
| `type` | String | `patient_registered`, `attempt_review_recommended`, `plan_regenerated` |
| `patient_id` | UUID (nullable) | |
| `plan_id` | UUID (nullable) | |
| `attempt_id` | UUID (nullable) | |
| `message` | Text | |
| `is_read` | Boolean | |
| `read_at` | DateTime (nullable) | |
| `created_at` | DateTime | |

---

### `patient_notification`

| Column | Type | Notes |
|--------|------|-------|
| `notification_id` | UUID (PK) | |
| `patient_id` | UUID (FK) | |
| `type` | String | `therapist_approved`, `plan_updated`, `daily_task_reminder` |
| `plan_id` | UUID (nullable) | |
| `assignment_id` | UUID (nullable) | |
| `message` | Text | |
| `is_read` | Boolean | |
| `read_at` | DateTime (nullable) | |
| `created_at` | DateTime | |

---

## Key Relationships Summary

```
therapist 1──* patient                     (assigned_therapist_id)
therapist 1──* therapy_plan
patient   1──* therapy_plan
therapy_plan 1──* plan_task_assignment
plan_task_assignment *──1 task
task      1──* task_level
task_level 1──* prompt
prompt    1──1 adaptive_threshold          (optional override)
task      1──1 task_scoring_weights        (one config per task)
task      *──* defect                      (via task_defect_mapping)
defect    1──1 defect_pa_threshold
baseline_assessment 1──* baseline_section
baseline_section    1──* baseline_item
baseline_assessment *──* defect            (via baseline_defect_mapping)
patient   1──* patient_baseline_result
patient_baseline_result 1──* baseline_item_result
session   1──* session_prompt_attempt
session_prompt_attempt 1──1 attempt_score_detail
patient   1──* patient_task_progress
task      1──* patient_task_progress
```
