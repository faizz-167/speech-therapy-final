# SpeechPath — Finalized Database Design v2.0

> **Single source of truth for the SpeechPath database schema.**
> Incorporates all analysis findings: prompt table consolidation, ORM drift resolution,
> missing constraint enforcement, string-to-date type corrections, live-only table
> formalisation, and three new recommended tables.
> Last updated: April 2026

---

## Table of Contents

1. [Overview](#1-overview)
2. [What Changed from v1](#2-what-changed-from-v1)
3. [Domain 1 — Identity](#3-domain-1--identity)
4. [Domain 2 — Clinical Content Catalog](#4-domain-2--clinical-content-catalog)
5. [Domain 3 — Baseline Assessment](#5-domain-3--baseline-assessment)
6. [Domain 4 — Therapy Planning](#6-domain-4--therapy-planning)
7. [Domain 5 — Session Runtime & Scoring](#7-domain-5--session-runtime--scoring)
8. [Domain 6 — Operations](#8-domain-6--operations)
9. [Relationships](#9-relationships)
10. [Unique Constraints](#10-unique-constraints)
11. [ID Strategy](#11-id-strategy)
12. [JSONB Usage](#12-jsonb-usage)
13. [Enum Reference](#13-enum-reference)
14. [Scoring Formula Reference](#14-scoring-formula-reference)
15. [ORM Model File Map](#15-orm-model-file-map)

---

## 1. Overview

SpeechPath uses a PostgreSQL relational database (hosted on Neon) accessed by two consumers:

- **FastAPI application** — SQLAlchemy 2.0 async engine via `asyncpg` (`DATABASE_URL`)
- **Celery ML scoring worker** — synchronous `psycopg2` (`DATABASE_URL_SYNC`)

The redesigned schema has **27 tables** across **6 domains**.

### Table Inventory

| Table | Domain | Purpose |
|---|---|---|
| `therapist` | Identity | Therapist user account — auth, code, professional profile |
| `patient` | Identity | Patient user account — auth, status, assigned therapist, streaks |
| `defect` | Content | Speech/language defect reference catalog |
| `task` | Content | Therapy exercise master catalog with WPM config |
| `task_level` | Content | Levelled difficulty tiers within each task |
| `prompt` | Content | Exercise prompts — includes speech target, evaluation, feedback and scoring config (merged) |
| `task_defect_mapping` | Content | Many-to-many bridge: tasks ↔ defects |
| `task_scoring_weights` | Content | Per-task Formula v2 scoring weights, rules, and adaptive thresholds |
| `adaptive_threshold` | Content | Per-prompt adaptive cutoff overrides |
| `defect_pa_threshold` | Content | Defect-specific phoneme accuracy pass thresholds |
| `emotion_weights_config` | Content | Age-group emotion weighting for engagement scoring |
| `baseline_assessment` | Baseline | Reusable baseline assessment template |
| `baseline_defect_mapping` | Baseline | Many-to-many bridge: baselines ↔ defects |
| `baseline_section` | Baseline | Ordered section groups within a baseline assessment |
| `baseline_item` | Baseline | Ordered individual diagnostic exercises within a section |
| `patient_baseline_result` | Baseline | Completed baseline result header for a patient |
| `baseline_item_result` | Baseline | Item-level scores under a patient baseline result |
| `therapy_plan` | Planning | Therapist-authored weekly treatment plan for a patient |
| `plan_task_assignment` | Planning | Scheduled task slots within a therapy plan |
| `plan_revision_history` | Planning | Audit log of every Kanban edit to a plan |
| `session` | Scoring | Therapy or baseline session header |
| `session_prompt_attempt` | Scoring | One audio attempt for one prompt within a session |
| `attempt_score_detail` | Scoring | Full ML pipeline output and scoring breakdown per attempt |
| `patient_task_progress` | Scoring | Rolling adaptive difficulty state per patient-task pair |
| `session_emotion_summary` | Scoring | Per-session emotion and engagement trends |
| `audio_file` | Operations | Audio upload tracking for cleanup and session replay |
| `therapist_notification` | Operations | Pending approval and clinical event notifications |

---

## 2. What Changed from v1

> The live database schema is **not changed** — all changes are additive column additions
> to ORM model classes, or new tables not yet in the ORM. The database itself is already
> ahead of the v1 ORM models.

| Change | Tables Affected | Reason |
|---|---|---|
| **Merged into `prompt`** | `speech_target`, `evaluation_target`, `feedback_rule`, `prompt_scoring` (4 tables removed) | All were 1-to-1 with `prompt`, always read together by the Celery worker. Eliminates 4 JOINs on every attempt scoring event. |
| **ORM models added** | `adaptive_threshold`, `defect_pa_threshold`, `emotion_weights_config` | Existed in live DB with no SQLAlchemy model. Scoring engine was silently ignoring them. |
| **New tables added** | `audio_file`, `therapist_notification`, `plan_revision_history` | Enable: audio cleanup + session replay, push notifications, clinical audit trail and PDF exports. |
| **Type fixes** | `patient.date_of_birth`, `patient_baseline_result.assessed_on`, `therapy_plan.start_date`, `therapy_plan.end_date`, `session_emotion_summary.session_date` | Were stored as `VARCHAR`. Changed to `DATE` for correct filtering, sorting, and range queries. |
| **Unique constraints added** | `patient_task_progress`, `task_defect_mapping`, `baseline_defect_mapping`, `plan_task_assignment` | Business-level uniqueness was intended but not enforced. Risk of duplicate rows corrupting adaptive state. |
| **ORM drift resolved** | 13 tables — 30+ missing columns added to models | Columns present in live DB were invisible to SQLAlchemy. See [Section 15](#15-orm-model-file-map). |

---

## 3. Domain 1 — Identity

### `therapist`

Therapist user accounts. The unique 8-character `therapist_code` is used by patients during self-registration. `role` is kept for JWT compatibility.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `therapist_id` | `UUID` | No | PK | `uuid4` |
| `therapist_code` | `VARCHAR(8)` | No | UNIQUE | 8-char patient registration code |
| `full_name` | `VARCHAR` | No | | |
| `email` | `VARCHAR` | No | UNIQUE | Login identifier |
| `password_hash` | `VARCHAR` | No | | bcrypt via passlib |
| `license_number` | `VARCHAR` | Yes | | |
| `specialization` | `VARCHAR` | Yes | | |
| `years_of_experience` | `INTEGER` | Yes | | |
| `role` | `VARCHAR` | No | | Default: `therapist` — kept for JWT |
| `created_at` | `TIMESTAMPTZ` | No | | Default: `now()` UTC |

---

### `patient`

Patient user accounts. Pending patients cannot access exercises until a therapist approves them.

> **FIX:** `date_of_birth` changed from `VARCHAR` → `DATE`.
> `pre_assigned_defect_ids` is deprecated — use `task_defect_mapping` instead.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `patient_id` | `UUID` | No | PK | `uuid4` |
| `email` | `VARCHAR` | No | UNIQUE | Login identifier |
| `password_hash` | `VARCHAR` | No | | bcrypt via passlib |
| `full_name` | `VARCHAR` | No | | |
| `date_of_birth` | `DATE` | No | | **FIXED** — was `VARCHAR` |
| `gender` | `VARCHAR` | Yes | | |
| `primary_diagnosis` | `TEXT` | Yes | | |
| `clinical_notes` | `TEXT` | Yes | | |
| `pre_assigned_defect_ids` | `JSONB` | Yes | | Deprecated — use `task_defect_mapping` |
| `current_streak` | `INTEGER` | No | | Default: `0` |
| `longest_streak` | `INTEGER` | No | | Default: `0` |
| `assigned_therapist_id` | `UUID` | Yes | FK → `therapist.therapist_id` | |
| `status` | `ENUM(patient_status)` | No | | `pending` \| `approved` |
| `role` | `VARCHAR` | No | | Default: `patient` |
| `created_at` | `TIMESTAMPTZ` | No | | Default: `now()` UTC |

---

## 4. Domain 2 — Clinical Content Catalog

### Design note — two scoring systems in parallel

This domain contains two distinct scoring configurations that must not be confused:

| Config | Table | Purpose | Used when |
|---|---|---|---|
| `ideal_wpm_min/max`, `wpm_tolerance` | `task` | Expected speech rate range for this task type | Therapy-time SRS component |
| `task_scoring_weights` | `task` | Full Formula v2 weights + post-composite rules | Therapy-time adaptive scoring |
| `formula_mode`, `formula_weights`, `fusion_weights`, `wpm_range`, `max_score` | `baseline_item` | Diagnostic assessment scoring — different clinical moment | Baseline assessment only |

They are parallel systems, not redundant ones. Baseline scoring happens before therapy begins (diagnostic); `task_scoring_weights` drives ongoing adaptive therapy scoring.

---

### `defect`

Speech and language defect reference catalog. 33 rows in production.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `defect_id` | `VARCHAR` | No | PK | Domain string ID |
| `code` | `VARCHAR` | No | UNIQUE | Business code |
| `name` | `VARCHAR` | No | | |
| `category` | `ENUM(defect_category)` | No | | |
| `description` | `TEXT` | Yes | | |

---

### `task`

Therapy exercise master catalog. WPM columns define the **expected speech rate range** for each task type, used to compute the speech rate score (SRS) component of Formula v2.

**WPM column rationale:**
- `ideal_wpm_min` / `ideal_wpm_max` — the range where `SRS = 1.0` (full marks)
- `wpm_tolerance` — how far outside the range before `SRS = 0`. Within tolerance = partial linear decay
- These are task-type defaults. A phoneme repetition task expects 40–70 WPM; a reading task expects 100–140 WPM. They live on `task` (not `task_level` or `prompt`) because the rate expectation reflects the exercise category, not the difficulty level.

> **ORM drift resolved:** `source_id`, `created_at` added.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `task_id` | `VARCHAR` | No | PK | Domain string ID |
| `name` | `VARCHAR` | No | | |
| `type` | `ENUM(task_type)` | No | | |
| `task_mode` | `ENUM(task_mode_type)` | No | | |
| `description` | `TEXT` | Yes | | |
| `ideal_wpm_min` | `INTEGER` | No | | Default: `80`. Floor of ideal speech rate |
| `ideal_wpm_max` | `INTEGER` | No | | Default: `120`. Ceiling of ideal speech rate |
| `wpm_tolerance` | `INTEGER` | No | | Default: `20`. Partial credit band beyond ideal range |
| `source_id` | `VARCHAR` | Yes | | **ADDED** — content lineage tracking |
| `created_at` | `TIMESTAMPTZ` | No | | **ADDED** — Default: `now()` UTC |

---

### `task_level`

Levelled difficulty tiers within each task. One task has many levels.

> **ORM drift resolved:** `source_level_id` added.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `level_id` | `VARCHAR` | No | PK | Domain string ID |
| `task_id` | `VARCHAR` | No | FK → `task.task_id` | |
| `level_name` | `ENUM(level_name)` | No | | |
| `difficulty_score` | `INTEGER` | No | | Numeric difficulty rank |
| `source_level_id` | `VARCHAR` | Yes | | **ADDED** — level lineage tracking |

---

### `prompt` ★ Consolidated

Exercise prompts shown to patients during sessions. **The four former satellite tables (`speech_target`, `evaluation_target`, `feedback_rule`, `prompt_scoring`) are merged here.** All were one-to-one with `prompt` and always read together by the Celery worker — merging reduces the worker's per-attempt DB reads from 5 to 1.

> **ORM drift resolved:** `source_prompt_id` added.

**Core prompt fields:**

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `prompt_id` | `VARCHAR` | No | PK | Domain string ID |
| `level_id` | `VARCHAR` | No | FK → `task_level.level_id` | |
| `prompt_type` | `ENUM(prompt_type_enum)` | No | | Default: `exercise` |
| `task_mode` | `VARCHAR` | No | | Runtime snapshot from `task_level` |
| `scenario_context` | `TEXT` | Yes | | |
| `instruction` | `TEXT` | Yes | | |
| `display_content` | `TEXT` | Yes | | Visible text/content shown to patient |
| `target_response` | `TEXT` | Yes | | Expected spoken response |
| `accuracy_check` | `TEXT` | Yes | | |
| `evaluation_criteria` | `VARCHAR` | Yes | | |
| `source_prompt_id` | `VARCHAR` | Yes | | **ADDED** — prompt lineage tracking |

**Merged from `speech_target`:**

| Column | Type | Null | Notes |
|---|---|---|---|
| `speech_target` | `JSONB` | Yes | **MERGED** — was `speech_target.raw_speech_target`. Flexible ML speech config for HuBERT. |

**Merged from `evaluation_target`:**

| Column | Type | Null | Notes |
|---|---|---|---|
| `eval_scope` | `VARCHAR` | Yes | **MERGED** — was `evaluation_target.scope`. Word-level, sentence-level, etc. |
| `target_phonemes` | `JSONB` | Yes | **MERGED** — was `evaluation_target.target_phonemes`. Phoneme list for HuBERT alignment. |

**Merged from `feedback_rule`:**

| Column | Type | Null | Notes |
|---|---|---|---|
| `pass_message` | `TEXT` | Yes | **MERGED** — was `feedback_rule.pass_message` |
| `partial_message` | `TEXT` | Yes | **MERGED** — was `feedback_rule.partial_message` |
| `fail_message` | `TEXT` | Yes | **MERGED** — was `feedback_rule.fail_message` |

**Merged from `prompt_scoring`:**

| Column | Type | Null | Notes |
|---|---|---|---|
| `active` | `BOOLEAN` | No | **MERGED** — Default: `true` |
| `tc_mode` | `VARCHAR` | Yes | **MERGED** — task completion evaluation mode |
| `target_word_count` | `INTEGER` | Yes | **MERGED** |
| `target_duration_sec` | `INTEGER` | Yes | **MERGED** |
| `min_length_words` | `INTEGER` | Yes | **MERGED** |
| `aq_relevance_threshold` | `NUMERIC` | No | **MERGED** — Default: `0.60` |

---

### `task_defect_mapping`

Many-to-many bridge between tasks and defects.

> **Constraint added:** `UNIQUE(task_id, defect_id)` — prevents duplicate mappings inflating plan generation.
> **ORM drift resolved:** `clinical_notes` added.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `mapping_id` | `VARCHAR` | No | PK | Domain string ID |
| `task_id` | `VARCHAR` | No | FK → `task.task_id` | |
| `defect_id` | `VARCHAR` | No | FK → `defect.defect_id` | |
| `relevance_level` | `VARCHAR` | Yes | | Strength/classification |
| `clinical_notes` | `TEXT` | Yes | | **ADDED** |

**Unique constraint:** `UNIQUE(task_id, defect_id)`

---

### `task_scoring_weights`

Per-task Formula v2 scoring weights and post-composite clinical rules. One-to-one with `task`.

**Rule column rationale — these are not weights, they are post-composite guardrails:**

| Rule columns | What they do |
|---|---|
| `rule_severe_pa_threshold` / `rule_severe_pa_score_cap` | If `phoneme_accuracy < threshold`, cap `final_score` at `score_cap` regardless of other components. Prevents a patient who mispronounced most phonemes from passing on fluency and emotion alone. Configurable per task because different defect types have different clinically meaningful PA floors. |
| `rule_low_eng_threshold` / `rule_low_eng_penalty` | If `engagement_score < threshold`, deduct `penalty` from `final_score`. A patient who is highly disengaged gets an additional deduction on top of what the engagement weight already contributes. This double-counts low engagement intentionally — it is a clinical signal of non-participation. |
| `rule_high_eng_threshold` / `rule_high_eng_boost` | If `engagement_score > threshold`, add `boost` to `final_score`. Rewards genuine high-affect participation beyond what the weighted formula captures. |
| `rule_low_conf_threshold` | If Whisper ASR confidence < threshold, set `low_confidence_flag = true` and `review_recommended = true` on the attempt. Not a score modifier — a quality gate. When ASR confidence is low, every downstream score is computed against an unreliable transcript. Configurable because simple vocabulary tasks warrant a tighter threshold than spontaneous speech tasks. |

> **ORM drift resolved:** 10 columns added — `adaptive_advance_lookback_count`, `adaptive_advance_lookback_threshold`, `adaptive_consecutive_fail_ceiling`, `rule_low_conf_threshold`, `version`, `notes`, `approved_by`, `approved_at`, `created_at`, `updated_at`.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `weight_id` | `VARCHAR` | No | PK | Domain string ID |
| `task_id` | `VARCHAR` | No | FK, UNIQUE → `task.task_id` | One-to-one |
| `speech_w_pa` | `NUMERIC` | No | | Phoneme accuracy weight. Default: `0.40` |
| `speech_w_wa` | `NUMERIC` | No | | Word accuracy weight. Default: `0.30` |
| `speech_w_fs` | `NUMERIC` | No | | Fluency score weight. Default: `0.15` |
| `speech_w_srs` | `NUMERIC` | No | | Speech rate score weight. Default: `0.10` |
| `speech_w_cs` | `NUMERIC` | No | | Confidence score weight. Default: `0.05` |
| `fusion_w_speech` | `NUMERIC` | No | | Default: `0.90` |
| `fusion_w_engagement` | `NUMERIC` | No | | Default: `0.10` |
| `engagement_w_emotion` | `NUMERIC` | No | | Default: `0.65` |
| `engagement_w_behavioral` | `NUMERIC` | No | | Default: `0.35` |
| `behavioral_w_rl` | `NUMERIC` | No | | Response latency weight. Default: `0.40` |
| `behavioral_w_tc` | `NUMERIC` | No | | Task completion weight. Default: `0.35` |
| `behavioral_w_aq` | `NUMERIC` | No | | Answer quality weight. Default: `0.25` |
| `adaptive_advance_threshold` | `NUMERIC` | No | | Score to advance level. Default: `75.0` |
| `adaptive_stay_min` | `NUMERIC` | No | | Stay range floor. Default: `55.0` |
| `adaptive_stay_max` | `NUMERIC` | No | | Stay range ceiling. Default: `74.0` |
| `adaptive_drop_threshold` | `NUMERIC` | No | | Score to drop level. Default: `55.0` |
| `adaptive_consecutive_fail_limit` | `INTEGER` | No | | Default: `3` |
| `adaptive_advance_lookback_count` | `INTEGER` | Yes | | **ADDED** — lookback window size for advance decision |
| `adaptive_advance_lookback_threshold` | `NUMERIC` | Yes | | **ADDED** — required score in lookback window |
| `adaptive_consecutive_fail_ceiling` | `INTEGER` | Yes | | **ADDED** — hard ceiling for consecutive fails before drop |
| `rule_severe_pa_threshold` | `NUMERIC` | No | | PA cap trigger. Default: `35.0` |
| `rule_severe_pa_score_cap` | `NUMERIC` | No | | Max final score when PA is severe. Default: `45.0` |
| `rule_low_eng_threshold` | `NUMERIC` | No | | Low engagement trigger. Default: `35.0` |
| `rule_low_eng_penalty` | `NUMERIC` | No | | Points deducted for low engagement. Default: `5.0` |
| `rule_high_eng_threshold` | `NUMERIC` | No | | High engagement trigger. Default: `85.0` |
| `rule_high_eng_boost` | `NUMERIC` | No | | Points added for high engagement. Default: `5.0` |
| `rule_low_conf_threshold` | `NUMERIC` | Yes | | **ADDED** — Whisper ASR confidence quality gate |
| `version` | `INTEGER` | No | | **ADDED** — Default: `1` |
| `notes` | `TEXT` | Yes | | **ADDED** — clinical rationale |
| `approved_by` | `VARCHAR` | Yes | | **ADDED** |
| `approved_at` | `TIMESTAMPTZ` | Yes | | **ADDED** |
| `created_at` | `TIMESTAMPTZ` | No | | **ADDED** — Default: `now()` UTC |
| `updated_at` | `TIMESTAMPTZ` | Yes | | **ADDED** — set on every update |

---

### `adaptive_threshold` ★ ORM Model Added

Per-prompt adaptive cutoff overrides. Existed in live DB with no ORM model — scoring engine was falling back to `task_scoring_weights` defaults for all prompts equally.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `threshold_id` | `VARCHAR` | No | PK | Domain string ID |
| `prompt_id` | `VARCHAR` | No | FK, UNIQUE → `prompt.prompt_id` | One-to-one |
| `advance_to_next_level` | `NUMERIC` | Yes | | Overrides `task_scoring_weights.adaptive_advance_threshold` for this prompt |
| `stay_at_current_level_min` | `NUMERIC` | Yes | | |
| `stay_at_current_level_max` | `NUMERIC` | Yes | | |

---

### `defect_pa_threshold` ★ ORM Model Added

Defect-specific phoneme accuracy pass thresholds. Feeds the PA cap rule in `scoring/engine.py`. Without an ORM model, the engine applied the hardcoded `35.0` threshold uniformly across all defects — clinically inaccurate.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `threshold_id` | `VARCHAR` | No | PK | Domain string ID |
| `defect_id` | `VARCHAR` | No | FK → `defect.defect_id` | |
| `min_pa_to_pass` | `NUMERIC` | No | | Required phoneme accuracy to pass for this defect |
| `target_phonemes` | `VARCHAR[]` | Yes | | Array of phoneme strings |
| `phoneme_scope` | `VARCHAR` | Yes | | |
| `severity_modifier` | `NUMERIC` | No | | Default: `1.0` |
| `notes` | `TEXT` | Yes | | |
| `created_at` | `TIMESTAMPTZ` | No | | Default: `now()` UTC |

---

### `emotion_weights_config` ★ ORM Model Added

Age-group emotion weighting for the SpeechBrain engagement scoring path. Without an ORM model, the engagement score used a single undifferentiated weight profile for all patients regardless of age group.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `config_id` | `VARCHAR` | No | PK | Domain string ID |
| `age_group` | `VARCHAR` | No | UNIQUE | e.g. `child`, `adult`, `senior` |
| `w_happy` | `NUMERIC` | No | | Default: `0` |
| `w_excited` | `NUMERIC` | No | | Default: `0` |
| `w_neutral` | `NUMERIC` | No | | Default: `0` |
| `w_surprised` | `NUMERIC` | No | | Default: `0` |
| `w_sad` | `NUMERIC` | No | | Default: `0` |
| `w_angry` | `NUMERIC` | No | | Default: `0` |
| `w_fearful` | `NUMERIC` | No | | Default: `0` |
| `w_positive_affect` | `NUMERIC` | No | | Default: `0` |
| `w_focused` | `NUMERIC` | No | | Default: `0` |
| `version` | `INTEGER` | No | | Default: `1` |
| `approved_by` | `VARCHAR` | Yes | | |
| `approved_at` | `TIMESTAMPTZ` | Yes | | |
| `created_at` | `TIMESTAMPTZ` | No | | Default: `now()` UTC |

---

## 5. Domain 3 — Baseline Assessment

### Why this domain has its own scoring config

Baseline assessment is a **three-level diagnostic hierarchy** — `baseline_assessment → baseline_section → baseline_item` — that exists entirely *before* therapy begins. Its purpose is to determine starting difficulty level, not to adaptively score ongoing therapy.

Because there is no `task` or `task_scoring_weights` involved, baseline items carry their own scoring configuration:

| `baseline_item` column | Purpose | Why it cannot come from `task_scoring_weights` |
|---|---|---|
| `expected_output` | Full expected spoken response — used for word accuracy (WA) | Therapy prompts have `target_response`; baseline items are diagnostic and may have multi-sentence or clinician-described expected outputs |
| `target_phoneme` | Single phoneme being assessed in this item (e.g. `/s/`) | Narrows HuBERT alignment to one sound. Different from `target_phonemes` JSONB on `prompt` which is a list for therapy. |
| `formula_mode` | Which scoring approach applies: `auto_full`, `auto_phoneme_only`, `clinician_rated`, `auto_simple` | Some baseline items are clinician-scored (manual), some only need phoneme accuracy — `task_scoring_weights` only supports full automated scoring |
| `formula_weights` | Per-item Formula v2 weight overrides | A stuttering baseline item might weight fluency at 0.70 — measuring a different clinical construct than a standard therapy task |
| `fusion_weights` | Speech/engagement fusion overrides for this item | |
| `wpm_range` | Expected WPM range for this diagnostic item | `task.ideal_wpm_min/max` are calibrated for ongoing therapy; baseline has no established patient WPM yet — age-appropriate and defect-appropriate ranges are used instead |
| `max_score` | Ordinal scale ceiling for clinician-rated items | A diadochokinesis item scored 0–3 needs `max_score=3` to normalize to 0–100 for the aggregate `raw_score`. Not applicable to automated therapy scoring. |

---

### `baseline_assessment`

Reusable assessment template. One assessment has many sections.

> **ORM drift resolved:** `administration_method`, `created_at` added.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `baseline_id` | `VARCHAR` | No | PK | Domain string ID |
| `code` | `VARCHAR` | No | UNIQUE | |
| `name` | `VARCHAR` | No | | |
| `domain` | `ENUM(baseline_domain)` | No | | |
| `description` | `TEXT` | Yes | | |
| `administration_method` | `ENUM(administration_method)` | Yes | | **ADDED** |
| `created_at` | `TIMESTAMPTZ` | No | | **ADDED** — Default: `now()` UTC |

---

### `baseline_defect_mapping`

Many-to-many bridge between baseline assessments and defects.

> **Constraint added:** `UNIQUE(baseline_id, defect_id)`
> **ORM drift resolved:** `relevance_level`, `clinical_notes` added.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `mapping_id` | `VARCHAR` | No | PK | Domain string ID |
| `baseline_id` | `VARCHAR` | No | FK → `baseline_assessment.baseline_id` | |
| `defect_id` | `VARCHAR` | No | FK → `defect.defect_id` | |
| `relevance_level` | `VARCHAR` | Yes | | **ADDED** |
| `clinical_notes` | `TEXT` | Yes | | **ADDED** |

**Unique constraint:** `UNIQUE(baseline_id, defect_id)`

---

### `baseline_section`

Ordered section groups within a baseline assessment. Sections exist as a real entity because:
- The frontend renders a section header and instructions once, then walks through all items in that section
- `target_defect_id` links each section to a specific defect — used by `plan_generator.py` to select which sections are clinically relevant for a patient's diagnosed defects
- Collapsing sections into `baseline_item` would require duplicating section metadata on every item row

> **ORM drift resolved:** `target_defect_id` added.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `section_id` | `VARCHAR` | No | PK | Domain string ID |
| `baseline_id` | `VARCHAR` | No | FK → `baseline_assessment.baseline_id` | |
| `section_name` | `VARCHAR` | No | | |
| `instructions` | `TEXT` | Yes | | Shown once before all items in this section |
| `order_index` | `INTEGER` | No | | Section sequence within assessment |
| `target_defect_id` | `VARCHAR` | Yes | FK → `defect.defect_id` | **ADDED** — section-to-defect link for plan generation |

---

### `baseline_item`

Ordered individual diagnostic exercises within a section.

> **ORM drift resolved:** `defect_phoneme_focus`, `image_keyword`, `reference_text`, `scope`, `scoring_method` added.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `item_id` | `VARCHAR` | No | PK | Domain string ID |
| `section_id` | `VARCHAR` | No | FK → `baseline_section.section_id` | |
| `order_index` | `INTEGER` | No | | Item sequence within section |
| `task_name` | `VARCHAR` | Yes | | |
| `instruction` | `TEXT` | Yes | | |
| `display_content` | `TEXT` | Yes | | Content shown to patient |
| `expected_output` | `TEXT` | Yes | | Full expected spoken response — used for WA computation |
| `response_type` | `VARCHAR` | Yes | | |
| `target_phoneme` | `VARCHAR` | Yes | | Single phoneme focus for HuBERT alignment (e.g. `/s/`) |
| `formula_mode` | `VARCHAR` | Yes | | `auto_full` \| `auto_phoneme_only` \| `clinician_rated` \| `auto_simple` |
| `formula_weights` | `JSONB` | Yes | | Per-item Formula v2 weight overrides |
| `fusion_weights` | `JSONB` | Yes | | Speech/engagement fusion overrides |
| `wpm_range` | `JSONB` | Yes | | Diagnostic WPM reference range |
| `defect_codes` | `JSONB` | Yes | | Defect tag list for this item |
| `max_score` | `INTEGER` | Yes | | Ordinal scale ceiling for `clinician_rated` items |
| `defect_phoneme_focus` | `VARCHAR` | Yes | | **ADDED** |
| `image_keyword` | `VARCHAR` | Yes | | **ADDED** |
| `reference_text` | `TEXT` | Yes | | **ADDED** |
| `scope` | `VARCHAR` | Yes | | **ADDED** |
| `scoring_method` | `VARCHAR` | Yes | | **ADDED** |

---

### `patient_baseline_result`

Completed baseline result header per patient.

> **FIX:** `assessed_on` changed from `VARCHAR` → `DATE`.
> **ORM drift resolved:** `percentile` added.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `result_id` | `UUID` | No | PK | `uuid4` |
| `patient_id` | `UUID` | No | FK → `patient.patient_id` | |
| `baseline_id` | `VARCHAR` | No | FK → `baseline_assessment.baseline_id` | |
| `therapist_id` | `UUID` | No | FK → `therapist.therapist_id` | |
| `assessed_on` | `DATE` | No | | **FIXED** — was `VARCHAR` |
| `raw_score` | `INTEGER` | Yes | | Aggregate normalized score |
| `percentile` | `NUMERIC` | Yes | | **ADDED** |
| `severity_rating` | `VARCHAR` | Yes | | |
| `notes` | `TEXT` | Yes | | |

---

### `baseline_item_result`

Item-level scores under a patient baseline result.

> **ORM drift resolved:** `clinician_note` added.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `item_result_id` | `UUID` | No | PK | `uuid4` |
| `result_id` | `UUID` | No | FK → `patient_baseline_result.result_id` | |
| `item_id` | `VARCHAR` | No | FK → `baseline_item.item_id` | |
| `score_given` | `INTEGER` | Yes | | Clinician-assigned score (for `clinician_rated` mode) |
| `error_noted` | `TEXT` | Yes | | |
| `clinician_note` | `TEXT` | Yes | | **ADDED** |

---

## 6. Domain 4 — Therapy Planning

### `therapy_plan`

Therapist-authored weekly treatment plan. A plan moves from `draft` → `approved` after Kanban review.

> **FIX:** `start_date` and `end_date` changed from `VARCHAR` → `DATE`.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `plan_id` | `UUID` | No | PK | `uuid4` |
| `patient_id` | `UUID` | No | FK → `patient.patient_id` | |
| `therapist_id` | `UUID` | No | FK → `therapist.therapist_id` | |
| `plan_name` | `VARCHAR` | No | | |
| `start_date` | `DATE` | Yes | | **FIXED** — was `VARCHAR` |
| `end_date` | `DATE` | Yes | | **FIXED** — was `VARCHAR` |
| `status` | `VARCHAR` | No | | `draft` \| `approved` \| `archived`. Default: `draft` |
| `goals` | `TEXT` | Yes | | |
| `created_at` | `TIMESTAMPTZ` | No | | Default: `now()` UTC |

---

### `plan_task_assignment`

Scheduled task slots within a therapy plan (14 assignments per plan, 2 per day over 7 days).

> **Constraint added:** `UNIQUE(plan_id, day_index, priority_order)` — prevents Kanban drag-drop creating duplicate day slots.
> Cascade delete from `therapy_plan` is already set.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `assignment_id` | `UUID` | No | PK | `uuid4` |
| `plan_id` | `UUID` | No | FK → `therapy_plan.plan_id` | Cascade delete |
| `task_id` | `VARCHAR` | No | FK → `task.task_id` | |
| `therapist_id` | `UUID` | No | FK → `therapist.therapist_id` | |
| `day_index` | `INTEGER` | Yes | | `0–6` for 7-day plan |
| `priority_order` | `INTEGER` | Yes | | Within-day ordering (`1` or `2`) |
| `status` | `VARCHAR` | No | | Default: `pending` |
| `paused` | `BOOLEAN` | No | | Default: `false` |
| `clinical_rationale` | `TEXT` | Yes | | |

**Unique constraint:** `UNIQUE(plan_id, day_index, priority_order)`

---

### `plan_revision_history` ★ New Table

Audit log of every therapist edit to a plan via the Kanban board. Required for clinical audit trails and the planned PDF progress export feature.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `revision_id` | `UUID` | No | PK | `uuid4` |
| `plan_id` | `UUID` | No | FK → `therapy_plan.plan_id` | |
| `therapist_id` | `UUID` | No | FK → `therapist.therapist_id` | |
| `action` | `VARCHAR` | No | | `add_task` \| `remove_task` \| `reorder` \| `approve` \| `edit_goal` |
| `assignment_id` | `UUID` | Yes | FK → `plan_task_assignment.assignment_id` | If action affects a specific slot |
| `old_value` | `JSONB` | Yes | | State snapshot before change |
| `new_value` | `JSONB` | Yes | | State snapshot after change |
| `note` | `TEXT` | Yes | | Optional therapist comment |
| `created_at` | `TIMESTAMPTZ` | No | | Default: `now()` UTC |

---

## 7. Domain 5 — Session Runtime & Scoring

### `session`

Header for all patient activity. `plan_id` is nullable to support baseline sessions (which are not linked to a therapy plan).

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `session_id` | `UUID` | No | PK | `uuid4` |
| `plan_id` | `UUID` | Yes | FK → `therapy_plan.plan_id` | Null for baseline sessions |
| `patient_id` | `UUID` | No | FK → `patient.patient_id` | |
| `therapist_id` | `UUID` | Yes | FK → `therapist.therapist_id` | |
| `session_date` | `TIMESTAMPTZ` | No | | Default: `now()` UTC |
| `duration_minutes` | `INTEGER` | Yes | | |
| `session_type` | `VARCHAR` | No | | `therapy` \| `baseline`. Default: `therapy` |
| `session_notes` | `TEXT` | Yes | | |

---

### `session_prompt_attempt`

One audio attempt for one prompt within a session. Primary write target of the Celery scoring pipeline.

> **ORM drift resolved:** `response_latency_sec`, `therapist_override_note` added.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `attempt_id` | `UUID` | No | PK | `uuid4` |
| `session_id` | `UUID` | No | FK → `session.session_id` | |
| `prompt_id` | `VARCHAR` | No | FK → `prompt.prompt_id` | |
| `attempt_number` | `INTEGER` | No | | Default: `1` |
| `result` | `VARCHAR` | Yes | | `pass` \| `fail` \| `partial` |
| `accuracy_score` | `NUMERIC` | Yes | | |
| `asr_transcript` | `TEXT` | Yes | | Whisper transcript |
| `audio_file_path` | `VARCHAR` | Yes | | Path relative to `UPLOAD_DIR` |
| `task_mode` | `VARCHAR` | Yes | | Runtime snapshot |
| `prompt_type` | `VARCHAR` | Yes | | Runtime snapshot |
| `speech_detected` | `BOOLEAN` | No | | Default: `false` |
| `response_latency_sec` | `NUMERIC` | Yes | | **ADDED** — raw latency in seconds |
| `therapist_override_note` | `TEXT` | Yes | | **ADDED** — manual override comment |
| `mic_activated_at` | `TIMESTAMPTZ` | Yes | | |
| `speech_start_at` | `TIMESTAMPTZ` | Yes | | |
| `created_at` | `TIMESTAMPTZ` | No | | Default: `now()` UTC |

---

### `attempt_score_detail`

Full ML pipeline output and scoring breakdown for one attempt. One-to-one with `session_prompt_attempt`.

`asr_transcript` is intentionally duplicated from `session_prompt_attempt` as an **immutable audit snapshot** — the transcript at the time of scoring, preserved even if the attempt row is later updated.

> **ORM drift resolved:** `rl_seconds` added.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `detail_id` | `UUID` | No | PK | `uuid4` |
| `attempt_id` | `UUID` | No | FK, UNIQUE → `session_prompt_attempt.attempt_id` | One-to-one |
| `word_accuracy` | `NUMERIC` | Yes | | WA component |
| `phoneme_accuracy` | `NUMERIC` | Yes | | PA component |
| `fluency_score` | `NUMERIC` | Yes | | FS component |
| `disfluency_rate` | `NUMERIC` | Yes | | |
| `pause_score` | `NUMERIC` | Yes | | |
| `speech_rate_wpm` | `INTEGER` | Yes | | Raw WPM from Whisper |
| `speech_rate_score` | `NUMERIC` | Yes | | SRS component (normalized against `task.ideal_wpm_*`) |
| `confidence_score` | `NUMERIC` | Yes | | CS component — Whisper ASR confidence |
| `rl_score` | `NUMERIC` | Yes | | Response latency score (0–1 normalized) |
| `rl_seconds` | `NUMERIC` | Yes | | **ADDED** — raw latency value in seconds |
| `tc_score` | `NUMERIC` | Yes | | Task completion score |
| `aq_score` | `NUMERIC` | Yes | | Answer quality score |
| `behavioral_score` | `NUMERIC` | Yes | | Composite behavioral |
| `dominant_emotion` | `VARCHAR` | Yes | | SpeechBrain classification output |
| `emotion_score` | `NUMERIC` | Yes | | |
| `engagement_score` | `NUMERIC` | Yes | | |
| `speech_score` | `NUMERIC` | Yes | | Speech composite |
| `final_score` | `NUMERIC` | Yes | | `Speech × 0.90 + Engagement × 0.10` (with rule adjustments) |
| `adaptive_decision` | `VARCHAR` | Yes | | `advance` \| `stay` \| `drop` |
| `pass_fail` | `VARCHAR` | Yes | | |
| `fail_reason` | `TEXT` | Yes | | |
| `performance_level` | `VARCHAR` | Yes | | |
| `baseline_score_ref` | `NUMERIC` | Yes | | |
| `progress_delta` | `NUMERIC` | Yes | | |
| `progress_classification` | `VARCHAR` | Yes | | |
| `low_confidence_flag` | `BOOLEAN` | No | | Default: `false`. Set when Whisper confidence < `rule_low_conf_threshold` |
| `review_recommended` | `BOOLEAN` | No | | Default: `false` |
| `warmup_gate_passed` | `BOOLEAN` | Yes | | |
| `target_phoneme_results` | `JSONB` | Yes | | Per-phoneme HuBERT alignment detail |
| `asr_transcript` | `TEXT` | Yes | | Immutable audit snapshot of Whisper output at time of scoring |
| `audio_duration_sec` | `NUMERIC` | Yes | | |
| `created_at` | `TIMESTAMPTZ` | No | | Default: `now()` UTC |

---

### `patient_task_progress`

Rolling adaptive difficulty state per patient-task pair. One row per patient per task — drives the advance/stay/drop decision on subsequent attempts.

> **Constraint added:** `UNIQUE(patient_id, task_id)` — critical. Without this, duplicate rows corrupt the adaptive difficulty system.
> Currently 0 rows in production — the Celery `analysis.py` task is likely not yet writing to this table.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `progress_id` | `UUID` | No | PK | `uuid4` |
| `patient_id` | `UUID` | No | FK → `patient.patient_id` | |
| `task_id` | `VARCHAR` | No | FK → `task.task_id` | |
| `current_level_id` | `VARCHAR` | Yes | FK → `task_level.level_id` | |
| `consecutive_passes` | `INTEGER` | No | | Default: `0` |
| `consecutive_fails` | `INTEGER` | No | | Default: `0` |
| `overall_accuracy` | `NUMERIC` | Yes | | |
| `last_final_score` | `NUMERIC` | Yes | | |
| `baseline_score` | `NUMERIC` | Yes | | Starting score from baseline assessment |
| `total_attempts` | `INTEGER` | No | | Default: `0` |
| `sessions_at_level` | `INTEGER` | No | | Default: `0` |
| `level_locked_until` | `TIMESTAMPTZ` | Yes | | Prevents rapid level changes |
| `last_attempted_at` | `TIMESTAMPTZ` | Yes | | |

**Unique constraint:** `UNIQUE(patient_id, task_id)`

---

### `session_emotion_summary`

Per-session emotion and engagement aggregate. Powers the patient progress dashboard emotion charts.

> **FIX:** `session_date` changed from `VARCHAR` → `DATE`.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `summary_id` | `UUID` | No | PK | `uuid4` |
| `session_id` | `UUID` | No | FK → `session.session_id` | |
| `patient_id` | `UUID` | No | FK → `patient.patient_id` | |
| `session_date` | `DATE` | Yes | | **FIXED** — was `VARCHAR` |
| `dominant_emotion` | `VARCHAR` | Yes | | |
| `avg_frustration` | `NUMERIC` | Yes | | |
| `avg_engagement` | `NUMERIC` | Yes | | |
| `drop_count` | `INTEGER` | No | | Default: `0`. Number of level drops in this session |

---

## 8. Domain 6 — Operations

### `audio_file` ★ New Table

Tracks every audio upload. Enables:
1. **Scheduled cleanup** — Celery beat task can purge files where `purged_at IS NULL AND created_at < now() - interval '7 days'`
2. **Session replay** — therapist can retrieve audio by `attempt_id` or `session_id`

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `file_id` | `UUID` | No | PK | `uuid4` |
| `attempt_id` | `UUID` | Yes | FK → `session_prompt_attempt.attempt_id` | Null until attempt row is created |
| `patient_id` | `UUID` | No | FK → `patient.patient_id` | |
| `session_id` | `UUID` | No | FK → `session.session_id` | |
| `file_path` | `VARCHAR` | No | | Path relative to `UPLOAD_DIR` env var |
| `file_size_bytes` | `INTEGER` | Yes | | |
| `duration_sec` | `NUMERIC` | Yes | | From Whisper metadata |
| `mime_type` | `VARCHAR` | No | | e.g. `audio/webm`, `audio/wav` |
| `created_at` | `TIMESTAMPTZ` | No | | Default: `now()` UTC |
| `purged_at` | `TIMESTAMPTZ` | Yes | | `NULL` = file on disk. Set when file is deleted. |

---

### `therapist_notification` ★ New Table

Persistent notification log for therapists. Supports pending patient approvals, plan-ready events, and flagged attempt reviews. Enables the push notification feature from the future improvements backlog.

| Column | Type | Null | Key | Notes |
|---|---|---|---|---|
| `notification_id` | `UUID` | No | PK | `uuid4` |
| `therapist_id` | `UUID` | No | FK → `therapist.therapist_id` | |
| `type` | `VARCHAR` | No | | `patient_approval` \| `plan_ready` \| `review_flagged` |
| `patient_id` | `UUID` | Yes | FK → `patient.patient_id` | If applicable |
| `plan_id` | `UUID` | Yes | FK → `therapy_plan.plan_id` | If applicable |
| `attempt_id` | `UUID` | Yes | FK → `session_prompt_attempt.attempt_id` | If applicable |
| `message` | `TEXT` | No | | Human-readable notification text |
| `is_read` | `BOOLEAN` | No | | Default: `false` |
| `created_at` | `TIMESTAMPTZ` | No | | Default: `now()` UTC |
| `read_at` | `TIMESTAMPTZ` | Yes | | Set when therapist reads the notification |

---

## 9. Relationships

### One-to-many

| Parent | Child | FK column |
|---|---|---|
| `therapist` | `patient` | `patient.assigned_therapist_id` |
| `therapist` | `therapy_plan` | `therapy_plan.therapist_id` |
| `therapist` | `patient_baseline_result` | `patient_baseline_result.therapist_id` |
| `therapist` | `session` | `session.therapist_id` |
| `therapist` | `therapist_notification` | `therapist_notification.therapist_id` |
| `patient` | `therapy_plan` | `therapy_plan.patient_id` |
| `patient` | `session` | `session.patient_id` |
| `patient` | `patient_task_progress` | `patient_task_progress.patient_id` |
| `patient` | `patient_baseline_result` | `patient_baseline_result.patient_id` |
| `patient` | `session_emotion_summary` | `session_emotion_summary.patient_id` |
| `patient` | `audio_file` | `audio_file.patient_id` |
| `task` | `task_level` | `task_level.task_id` |
| `task_level` | `prompt` | `prompt.level_id` |
| `therapy_plan` | `plan_task_assignment` | `plan_task_assignment.plan_id` — cascade delete |
| `therapy_plan` | `plan_revision_history` | `plan_revision_history.plan_id` |
| `baseline_assessment` | `baseline_section` | `baseline_section.baseline_id` |
| `baseline_section` | `baseline_item` | `baseline_item.section_id` |
| `patient_baseline_result` | `baseline_item_result` | `baseline_item_result.result_id` |
| `session` | `session_prompt_attempt` | `session_prompt_attempt.session_id` |
| `session` | `session_emotion_summary` | `session_emotion_summary.session_id` |
| `session` | `audio_file` | `audio_file.session_id` |

### One-to-one

| Table A | Table B | FK column |
|---|---|---|
| `task` | `task_scoring_weights` | `task_scoring_weights.task_id` |
| `prompt` | `adaptive_threshold` | `adaptive_threshold.prompt_id` |
| `session_prompt_attempt` | `attempt_score_detail` | `attempt_score_detail.attempt_id` |
| `session_prompt_attempt` | `audio_file` | `audio_file.attempt_id` |

### Many-to-many bridge tables

| Table A | Table B | Bridge |
|---|---|---|
| `task` | `defect` | `task_defect_mapping` |
| `baseline_assessment` | `defect` | `baseline_defect_mapping` |

### Lookup relationships (no ORM backref required)

| Table | Lookup target |
|---|---|
| `patient_task_progress.current_level_id` | `task_level.level_id` |
| `baseline_section.target_defect_id` | `defect.defect_id` |
| `defect_pa_threshold.defect_id` | `defect.defect_id` |

---

## 10. Unique Constraints

| Table | Constraint | Status |
|---|---|---|
| `therapist` | `UNIQUE(therapist_code)` | Existing |
| `therapist` | `UNIQUE(email)` | Existing |
| `patient` | `UNIQUE(email)` | Existing |
| `defect` | `UNIQUE(code)` | Existing |
| `task_scoring_weights` | `UNIQUE(task_id)` | Existing |
| `adaptive_threshold` | `UNIQUE(prompt_id)` | Existing |
| `emotion_weights_config` | `UNIQUE(age_group)` | Existing |
| `baseline_assessment` | `UNIQUE(code)` | Existing |
| `attempt_score_detail` | `UNIQUE(attempt_id)` | Existing |
| `task_defect_mapping` | `UNIQUE(task_id, defect_id)` | **ADDED** |
| `baseline_defect_mapping` | `UNIQUE(baseline_id, defect_id)` | **ADDED** |
| `patient_task_progress` | `UNIQUE(patient_id, task_id)` | **ADDED** |
| `plan_task_assignment` | `UNIQUE(plan_id, day_index, priority_order)` | **ADDED** |

---

## 11. ID Strategy

| Style | Tables | Rationale |
|---|---|---|
| `UUID` (`uuid4`) | `therapist`, `patient`, `therapy_plan`, `plan_task_assignment`, `plan_revision_history`, `session`, `session_prompt_attempt`, `attempt_score_detail`, `patient_baseline_result`, `baseline_item_result`, `patient_task_progress`, `session_emotion_summary`, `audio_file`, `therapist_notification` | Runtime-generated entities — must be globally unique, generated without coordination, safe to expose in URLs |
| `VARCHAR` domain ID | `defect`, `task`, `task_level`, `prompt`, `task_defect_mapping`, `task_scoring_weights`, `adaptive_threshold`, `defect_pa_threshold`, `emotion_weights_config`, `baseline_assessment`, `baseline_defect_mapping`, `baseline_section`, `baseline_item` | Curated seed/reference content — human-readable IDs support content authoring, debugging, and cross-environment seeding without UUID dependency |

---

## 12. JSONB Usage

JSONB is used only where payloads are genuinely flexible and expected to evolve faster than the relational schema. All other data is relational.

| Column | Table | Purpose |
|---|---|---|
| `pre_assigned_defect_ids` | `patient` | Deprecated — migration target is `task_defect_mapping` |
| `speech_target` | `prompt` | Merged from `speech_target` table — flexible ML speech config for HuBERT |
| `target_phonemes` | `prompt` | Merged from `evaluation_target` — phoneme list for HuBERT forced alignment |
| `formula_weights` | `baseline_item` | Per-item Formula v2 weight overrides for diagnostic scoring |
| `fusion_weights` | `baseline_item` | Per-item fusion weight overrides for diagnostic scoring |
| `wpm_range` | `baseline_item` | Age/defect-appropriate WPM range for diagnostic items |
| `defect_codes` | `baseline_item` | Defect tag list for the item |
| `target_phoneme_results` | `attempt_score_detail` | Per-phoneme HuBERT alignment output |
| `old_value` | `plan_revision_history` | Pre-change plan state snapshot |
| `new_value` | `plan_revision_history` | Post-change plan state snapshot |

---

## 13. Enum Reference

| Enum name | Values |
|---|---|
| `patient_status` | `pending`, `approved` |
| `task_type` | *(existing values in live DB)* |
| `task_mode_type` | *(existing values in live DB)* |
| `level_name` | *(existing values in live DB)* |
| `prompt_type_enum` | `exercise` + others |
| `baseline_domain` | *(existing values in live DB)* |
| `administration_method` | *(existing values in live DB)* |
| `defect_category` | *(existing values in live DB)* |

> All enums are PostgreSQL native types. `patient_status` uses `create_type=False` in the ORM,
> meaning the type must exist in the database before table creation. Do not drop and recreate
> enum types — use `ALTER TYPE ... ADD VALUE` for additions.

---

## 14. Scoring Formula Reference

The `attempt_score_detail` table is designed to persist every intermediate and final value of Formula v2.

```
Speech Score     = (PA × speech_w_pa)  + (WA × speech_w_wa)  + (FS × speech_w_fs)
                 + (SRS × speech_w_srs) + (CS × speech_w_cs)

Behavioral Score = (RL × behavioral_w_rl) + (TC × behavioral_w_tc) + (AQ × behavioral_w_aq)

Engagement Score = (Emotion × engagement_w_emotion) + (Behavioral × engagement_w_behavioral)

Final Score      = (Speech × fusion_w_speech) + (Engagement × fusion_w_engagement)

Post-composite rules (applied in order):
  if PA < rule_severe_pa_threshold   → Final = min(Final, rule_severe_pa_score_cap)
  if Engagement < rule_low_eng_threshold  → Final -= rule_low_eng_penalty
  if Engagement > rule_high_eng_threshold → Final += rule_high_eng_boost

Quality gate:
  if Whisper confidence < rule_low_conf_threshold
      → low_confidence_flag = true, review_recommended = true

Adaptive decision:
  Final >= adaptive_advance_threshold → advance level
  adaptive_stay_min <= Final <= adaptive_stay_max → stay at level
  Final < adaptive_drop_threshold → drop level
```

| Code | Component | Source in `attempt_score_detail` | Weight column in `task_scoring_weights` |
|---|---|---|---|
| PA | Phoneme Accuracy | `phoneme_accuracy` | `speech_w_pa` |
| WA | Word Accuracy | `word_accuracy` | `speech_w_wa` |
| FS | Fluency Score | `fluency_score` | `speech_w_fs` |
| SRS | Speech Rate Score | `speech_rate_score` (raw: `speech_rate_wpm`) | `speech_w_srs` |
| CS | Confidence Score | `confidence_score` | `speech_w_cs` |
| RL | Response Latency | `rl_score` (raw: `rl_seconds`) | `behavioral_w_rl` |
| TC | Task Completion | `tc_score` | `behavioral_w_tc` |
| AQ | Answer Quality | `aq_score` | `behavioral_w_aq` |

---

## 15. ORM Model File Map

All changes are **additive only** — no existing columns are renamed or removed. The database schema is not changed; Python model classes are updated to reflect what already exists in the live database.

| File | Class | Changes required |
|---|---|---|
| `models/users.py` | `Patient` | `date_of_birth`: `String` → `Date` |
| `models/content.py` | `Task` | Add: `source_id`, `created_at` |
| `models/content.py` | `TaskLevel` | Add: `source_level_id` |
| `models/content.py` | `Prompt` | Add all merged columns from 4 removed tables + `source_prompt_id`. **Remove classes:** `SpeechTarget`, `EvaluationTarget`, `FeedbackRule`, `PromptScoring` |
| `models/content.py` | `TaskDefectMapping` | Add: `clinical_notes` |
| `models/content.py` | `TaskScoringWeights` | Add: `adaptive_advance_lookback_count`, `adaptive_advance_lookback_threshold`, `adaptive_consecutive_fail_ceiling`, `rule_low_conf_threshold`, `version`, `notes`, `approved_by`, `approved_at`, `created_at`, `updated_at` |
| `models/content.py` | `AdaptiveThreshold` | **New class** — ORM model for `adaptive_threshold` table |
| `models/content.py` | `DefectPAThreshold` | **New class** — ORM model for `defect_pa_threshold` table |
| `models/content.py` | `EmotionWeightsConfig` | **New class** — ORM model for `emotion_weights_config` table |
| `models/baseline.py` | `BaselineAssessment` | Add: `administration_method`, `created_at` |
| `models/baseline.py` | `BaselineDefectMapping` | Add: `relevance_level`, `clinical_notes` |
| `models/baseline.py` | `BaselineSection` | Add: `target_defect_id` FK → `defect.defect_id` |
| `models/baseline.py` | `BaselineItem` | Add: `defect_phoneme_focus`, `image_keyword`, `reference_text`, `scope`, `scoring_method` |
| `models/baseline.py` | `PatientBaselineResult` | `assessed_on`: `String` → `Date`. Add: `percentile` |
| `models/baseline.py` | `BaselineItemResult` | Add: `clinician_note` |
| `models/plan.py` | `TherapyPlan` | `start_date`, `end_date`: `String` → `Date` |
| `models/plan.py` | `PlanRevisionHistory` | **New class** — new table (Section 6) |
| `models/scoring.py` | `SessionPromptAttempt` | Add: `response_latency_sec`, `therapist_override_note` |
| `models/scoring.py` | `AttemptScoreDetail` | Add: `rl_seconds` |
| `models/scoring.py` | `SessionEmotionSummary` | `session_date`: `String` → `Date` |
| `models/operations.py` | `AudioFile` | **New file + class** — new table (Section 8) |
| `models/operations.py` | `TherapistNotification` | **New file + class** — new table (Section 8) |

---

*End of document — SpeechPath Database Design v2.0*
