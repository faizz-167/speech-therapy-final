# SpeechPath Backend Flow Analysis

Last updated: 2026-04-06

## 1. What The Backend Does Today

The backend is split into four runtime layers:

1. FastAPI request layer
2. SQLAlchemy async persistence layer
3. Celery scoring worker
4. Redis WebSocket delivery

At a high level the current flow is:

1. Therapist or patient authenticates through `/auth/*`
2. Therapist approves patient and stores assigned defect IDs on `patient.pre_assigned_defect_ids`
3. Patient completes a simplified baseline flow
4. Therapist generates a weekly therapy plan from assigned defects + a baseline level
5. Patient starts a therapy session and uploads audio per prompt
6. Celery scores the attempt and writes `attempt_score_detail`
7. Score is pushed over Redis to `/ws/{patient_id}`
8. Patient progress APIs read scored attempts and whatever exists in `patient_task_progress`

The important distinction is this:

- The ORM model layer is mostly aligned with database v2
- The live backend logic is only partially aligned with database v2
- The biggest drift is in the scoring pipeline and the baseline flow

---

## 2. Current Backend Logic By Module

### 2.1 Auth and identity

Files:

- `server/app/routers/auth.py`
- `server/app/auth.py`
- `server/app/models/users.py`

Current behavior:

- Therapist registration creates a `therapist` row and returns a JWT
- Patient registration resolves `therapist_code`, creates a `patient` row with `status = pending`, and returns a JWT immediately
- Patient login is blocked until therapist approval
- `require_therapist()` and `require_patient()` load the user from DB on every protected request

Important implementation detail:

- Patient defect assignment is not normalized
- The code stores therapist-selected defect IDs in `patient.pre_assigned_defect_ids`
- This JSONB field is still the effective source of truth for assigned defects in the current backend

### 2.2 Therapist management

Files:

- `server/app/routers/therapist.py`

Current behavior:

- Dashboard counts therapist patients by status
- Patient listing returns profile + `pre_assigned_defect_ids`
- Approval sets:
  - `patient.status = approved`
  - `patient.pre_assigned_defect_ids = {"defect_ids": [...]}`
  - `patient.primary_diagnosis`
  - `patient.clinical_notes`
- Reject deletes the patient row
- Defect catalog is read from `defect`

What is missing relative to v2 schema:

- No `therapist_notification` row is created when a patient registers or is flagged

### 2.3 Baseline assessment flow

Files:

- `server/app/routers/baseline.py`
- `server/app/models/baseline.py`
- `client/app/patient/baseline/page.tsx`

Current behavior:

1. Backend reads patient defect IDs from `patient.pre_assigned_defect_ids`
2. It finds matching `baseline_assessment` rows through `baseline_defect_mapping`
3. It loads sections and items from `baseline_section` and `baseline_item`
4. It flattens items by category
5. It caps the entire baseline to 7 items total
6. Frontend records audio locally but does not upload it for ML scoring
7. Frontend asks patient to self-rate each item using 20/40/60/80/100
8. `/baseline/submit` averages those self-ratings and creates:
   - one `patient_baseline_result`
   - multiple `baseline_item_result`

The current baseline implementation is therefore not a clinical scoring engine. It is a lightweight self-rating workflow, and it should be replaced.

Major mismatches with the current schema:

- `baseline_item.formula_mode`, `formula_weights`, `fusion_weights`, `wpm_range`, `max_score`, `scoring_method`, and `scope` are not used
- `BaselineAssessment` boundaries are lost because the API merges multiple assessments into a synthetic category-based output
- `/baseline/submit` stores only one `baseline_id`, even if the items came from multiple actual baseline assessments
- No `session` row is created for baseline activity, even though `session.session_type = baseline` exists for that purpose
- No `session_prompt_attempt` rows exist for baseline audio items
- No ML-driven baseline scoring exists for `auto_simple` or `auto_phoneme_only`
- `clinician_rated` items are currently mixed into the same patient self-service flow, which is the wrong operational model

### 2.4 Therapy plan generation

Files:

- `server/app/services/plan_generator.py`
- `server/app/routers/plans.py`

Current behavior:

1. Read patient defect IDs from `patient.pre_assigned_defect_ids`
2. Find candidate tasks through `task_defect_mapping`
3. Filter tasks that have a `task_level.level_name` matching the requested baseline level
4. Fallback to `easy` if no tasks exist for that level
5. Create one `therapy_plan`
6. Create up to 14 `plan_task_assignment` rows for 7 days x 2 slots
7. Therapist can add, move, delete, and approve assignments through plan routes

What the current plan layer does correctly:

- Uses `task`, `task_level`, `task_defect_mapping`, `therapy_plan`, and `plan_task_assignment`
- Keeps plan generation tied to defect mapping rather than hardcoded tasks

What is missing relative to v2 schema:

- No `plan_revision_history` writes for generate, add, move, delete, approve, or regenerate
- `clinical_rationale` on `plan_task_assignment` is not populated
- No notification flow when a plan becomes ready
- Regeneration does not archive or supersede previous active plans

### 2.5 Patient task selection

Files:

- `server/app/routers/patient.py`

Current behavior:

- `/patient/tasks` returns today’s assignments from the latest approved plan
- `/patient/tasks/{assignment_id}/prompts` chooses which level to serve:
  - first from `patient_task_progress.current_level_id`
  - otherwise from latest `patient_baseline_result.severity_rating`
  - otherwise fallback to `easy`
- Once a level is chosen, it returns all `prompt` rows in that level

This is the effective adaptive entry point for therapy.

Limitation:

- The baseline fallback uses one global baseline severity for all tasks
- It does not resolve severity per defect or per baseline domain

### 2.6 Session creation and attempt upload

Files:

- `server/app/routers/session.py`
- `client/app/patient/tasks/[assignmentId]/page.tsx`
- `client/components/patient/Recorder.tsx`

Current behavior:

1. Patient opens an assignment page
2. Frontend calls:
   - `POST /session/start`
   - `GET /patient/tasks/{assignment_id}/prompts`
3. Backend creates a `session` row with `session_type = therapy`
4. Recorder captures:
   - raw audio blob
   - `micActivatedAt`
   - optional `speechStartAt`
5. Frontend uploads multipart form to `POST /session/{id}/attempt`
6. Backend:
   - validates session ownership
   - validates prompt metadata
   - writes the file to `UPLOAD_DIR`
   - creates `session_prompt_attempt`
   - stores prompt/task snapshots on the attempt row
   - triggers `analyze_attempt.delay(attempt_id)`

What is missing relative to v2 schema:

- No `audio_file` row is created
- `response_latency_sec` is not calculated and stored on `session_prompt_attempt`
- `accuracy_score` is not updated later
- Audio cleanup lifecycle is not tracked

### 2.7 Celery scoring pipeline

Files:

- `server/app/tasks/analysis.py`
- `server/app/scoring/engine.py`
- `server/app/ml/*`

Intended flow:

1. Load attempt + prompt context
2. Run Whisper ASR
3. Run HuBERT phoneme alignment
4. Run spaCy disfluency analysis
5. Run SpeechBrain emotion classification
6. Apply scoring formula
7. Write `attempt_score_detail`
8. Update `session_prompt_attempt`
9. Publish score to Redis

What actually happens today:

- The worker still queries old tables:
  - `prompt_scoring`
  - `speech_target`
- The database v2 consolidated those into `prompt`
- So the current worker logic is still written for the previous schema

This is the most important backend problem.

Additional scoring limitations:

- `score_attempt()` only uses the base task weights
- It ignores:
  - `adaptive_threshold`
  - `defect_pa_threshold`
  - `emotion_weights_config`
  - `task_scoring_weights.rule_low_conf_threshold`
  - `task_scoring_weights.adaptive_stay_max`
  - `adaptive_advance_lookback_count`
  - `adaptive_advance_lookback_threshold`
  - `adaptive_consecutive_fail_ceiling`
- `emotion_weights_config` is never loaded; emotion score is taken directly from the ML helper
- `patient_task_progress` is never inserted or updated
- `session_emotion_summary` is never inserted or updated
- `audio_file.duration_sec` is never backfilled
- `therapist_notification` is never created for flagged attempts

### 2.8 Progress APIs

Files:

- `server/app/routers/progress.py`

Current behavior:

- Reads `attempt_score_detail` joined with `session_prompt_attempt` and `session`
- Builds:
  - total attempts
  - average final score
  - pass rate
  - weekly trend
  - dominant emotion
- Reads `patient_task_progress` to build per-task metrics

Problem:

- The API expects `patient_task_progress` to exist
- The scoring worker never populates it
- So task metrics will stay empty or stale

### 2.9 WebSocket delivery

Files:

- `server/app/main.py`
- `client/lib/ws.ts`

Current behavior:

- Patient connects to `/ws/{patient_id}`
- First WS message must contain JWT
- Server subscribes to `ws:patient:{patient_id}` in Redis
- Celery publishes `score_ready`
- Frontend updates the score display immediately
- Polling exists as a fallback if WS delivery is delayed

This part is correctly aligned with the architecture and mostly independent from the schema redesign.

---

## 3. Where The Current Backend Still Depends On The Previous Database

### Critical old-schema dependency

`server/app/tasks/analysis.py` still reads:

- `prompt_scoring`
- `speech_target`

Those tables were removed from v2 and merged into `prompt`.

### Logical old-schema dependency

Even where the code compiles against v2 models, the business logic still behaves like the older design:

- baseline uses a simplified synthetic workflow rather than the richer baseline schema
- adaptive progression is not persisted
- per-prompt and per-defect threshold tables exist but are ignored
- operational tables (`audio_file`, `therapist_notification`, `plan_revision_history`) exist but are not used

---

## 4. Current Schema Coverage Matrix

### Tables actively used by runtime

- `therapist`
- `patient`
- `defect`
- `task`
- `task_level`
- `prompt`
- `task_defect_mapping`
- `task_scoring_weights`
- `baseline_assessment`
- `baseline_defect_mapping`
- `baseline_section`
- `baseline_item`
- `patient_baseline_result`
- `baseline_item_result`
- `therapy_plan`
- `plan_task_assignment`
- `session`
- `session_prompt_attempt`
- `attempt_score_detail`

### Tables modeled but effectively unused by runtime

- `adaptive_threshold`
- `defect_pa_threshold`
- `emotion_weights_config`
- `patient_task_progress`
- `session_emotion_summary`
- `audio_file`
- `therapist_notification`
- `plan_revision_history`

### Column groups present but ignored

On `prompt`:

- `speech_target`
- `target_phonemes`
- `pass_message`
- `partial_message`
- `fail_message`
- `tc_mode`
- `target_word_count`
- `target_duration_sec`
- `min_length_words`
- `aq_relevance_threshold`

On `baseline_item`:

- `formula_mode`
- `formula_weights`
- `fusion_weights`
- `wpm_range`
- `max_score`
- `scoring_method`
- `scope`
- `reference_text`
- `image_keyword`

On `task_scoring_weights`:

- `adaptive_stay_max`
- `adaptive_advance_lookback_count`
- `adaptive_advance_lookback_threshold`
- `adaptive_consecutive_fail_ceiling`
- `rule_low_conf_threshold`
- `notes`
- `approved_by`
- `approved_at`
- `updated_at`

---

## 5. How The Backend Should Work According To The Current Database

This section is the target implementation flow for database v2.

### 5.1 Patient approval and assigned defects

Given the current schema, there are two realistic options:

1. Short-term: continue using `patient.pre_assigned_defect_ids` as patient-specific assigned defects
2. Long-term: add a normalized `patient_defect` bridge table

Because the current database does not contain `patient_defect`, implementation should keep `pre_assigned_defect_ids` for now and treat:

- `task_defect_mapping` as content eligibility mapping
- `baseline_defect_mapping` as baseline eligibility mapping
- `patient.pre_assigned_defect_ids` as patient diagnosis assignment

### 5.2 Baseline flow aligned to v2

Target flow:

1. Therapist-assigned defects determine which `baseline_assessment` rows are relevant
2. API returns actual assessments, sections, and items without collapsing them into one synthetic category record
3. Patient baseline should include only ML-scoreable baseline items:
   - `auto_simple`
   - `auto_phoneme_only`
4. `clinician_rated` items must not appear in the patient self-service baseline flow
5. Frontend must not ask patients to self-rate anything
6. Patient records audio for each baseline item and uploads it through the same runtime pattern used by therapy attempts
7. Backend creates:
   - `session` with `session_type = baseline`
   - per-item attempt rows for that baseline session
   - Celery jobs for ML scoring
8. Celery scoring should reuse the therapy ML pipeline stages:
   - Whisper
   - HuBERT
   - spaCy disfluency
   - SpeechBrain emotion
9. Baseline scoring logic should branch by `baseline_item.formula_mode`:
   - `auto_phoneme_only`: score mainly from phoneme-focused ML outputs
   - `auto_simple`: score from a simpler composite using item config
10. Backend stores:
   - one `baseline_item_result` per item, using ML-derived score only
   - one `patient_baseline_result` per completed `baseline_assessment`
11. Severity should be computed from actual `baseline_item` configuration and ML outputs only

Hard rule:

- No patient self-rating scores should exist in the baseline workflow
- No baseline result should be derived from user-entered performance ratings

Recommended rule:

- Keep baseline scoring separate from therapy scoring
- Reuse the same ML execution pipeline, but not the same scoring formula blindly
- Use `baseline_item.formula_mode`, `formula_weights`, `fusion_weights`, `wpm_range`, `max_score`, and `scope` for baseline scoring
- Route `clinician_rated` items to a future therapist-administered baseline workflow instead of trying to auto-score or self-rate them

### 5.2.1 Baseline endpoint plan

Recommended endpoint shape:

1. `GET /baseline/exercises`
   - return only patient-facing, ML-scoreable baseline items
   - exclude `clinician_rated` items
2. `POST /baseline/start`
   - create a `session` row with `session_type = baseline`
   - bind the session to the patient and therapist
3. `POST /baseline/{session_id}/attempt`
   - upload one baseline item recording
   - persist the attempt
   - queue Celery scoring
4. `GET /baseline/attempt/{attempt_id}`
   - poll ML result exactly like therapy attempts
5. `POST /baseline/{session_id}/complete`
   - aggregate all ML-scored item results into:
     - `baseline_item_result`
     - `patient_baseline_result`

### 5.2.2 Baseline database write plan

For each ML-scored baseline item:

1. Save audio file
2. Create runtime attempt row for baseline recording
3. Insert ML result payload
4. Write `baseline_item_result` from ML output only:
   - `score_given`
   - `error_noted`
   - optional `clinician_note` remains null unless later added by therapist

After all items in one baseline assessment are finished:

1. Aggregate item-level ML scores
2. Create one `patient_baseline_result`
3. Set:
   - `raw_score`
   - `percentile` if the scoring model later supports it
   - `severity_rating`
   - `notes` if server-generated notes are added

### 5.2.3 Baseline scoring strategy

Do not treat baseline as a copy of therapy scoring.

Recommended baseline scoring logic:

1. `auto_phoneme_only`
   - prioritize `phoneme_accuracy`
   - optionally use `target_phoneme_results`
   - use transcript only as support data, not primary score driver
2. `auto_simple`
   - use a smaller composite based on:
     - word accuracy when target text exists
     - phoneme accuracy when relevant
     - fluency / WPM only when the baseline item config expects it
3. Emotion should not dominate baseline severity scoring unless explicitly configured in the baseline item
4. The baseline scorer should read:
   - `formula_mode`
   - `formula_weights`
   - `fusion_weights`
   - `wpm_range`
   - `max_score`
   - `scope`

### 5.2.4 Clinician-rated baseline items

`clinician_rated` items should be handled outside the patient self-service baseline.

Recommended policy:

1. Exclude them from the patient baseline UI entirely
2. Keep them in the schema and content catalog
3. Add a separate therapist/clinician assessment workflow later

This avoids two bad options:

- fake auto-scoring for items the ML pipeline cannot validly score
- patient self-rating for clinically rated tasks

### 5.3 Plan generation aligned to v2

Target flow:

1. Read patient defect IDs
2. Resolve eligible tasks from `task_defect_mapping`
3. Use baseline result to infer starting level per task or per defect domain
4. Create `therapy_plan`
5. Create ordered `plan_task_assignment` rows
6. Write `plan_revision_history` rows for:
   - generate
   - add_task
   - remove_task
   - reorder
   - approve
   - regenerate
7. When approved, create `therapist_notification` or patient-facing delivery event if needed

### 5.4 Session upload aligned to v2

Target flow for `POST /session/{id}/attempt`:

1. Validate session and prompt
2. Save physical audio file
3. Create `session_prompt_attempt`
4. Compute and persist `response_latency_sec`
5. Create matching `audio_file` row with:
   - `attempt_id`
   - `patient_id`
   - `session_id`
   - `file_path`
   - `file_size_bytes`
   - `mime_type`
6. Queue Celery task

### 5.5 Celery scoring flow aligned to v2

This is the main required redesign.

Target attempt context query should load from:

- `session_prompt_attempt`
- `session`
- `prompt`
- `task_level`
- `task`
- `task_scoring_weights`
- `adaptive_threshold` for prompt override
- patient defect IDs from `patient`
- matching `defect_pa_threshold` rows
- `emotion_weights_config` using patient age group

Target scoring flow:

1. Load attempt context from consolidated `prompt` table
2. Use `prompt.target_response` and `prompt.speech_target`
3. Use `prompt.target_phonemes` in HuBERT alignment when present
4. Compute:
   - WA
   - PA
   - FS
   - SRS from `task.ideal_wpm_*`
   - CS from Whisper confidence
   - RL from attempt timestamps
   - TC from `prompt.tc_mode`, `target_word_count`, `target_duration_sec`, `min_length_words`
   - AQ from transcript relevance and/or heuristics
5. Convert raw emotion model output into final emotion score using `emotion_weights_config`
6. Apply `task_scoring_weights`
7. Override adaptive thresholds from `adaptive_threshold` if present
8. Apply severe-PA logic using the patient’s assigned-defect thresholds from `defect_pa_threshold`
9. Apply low-confidence flag using `rule_low_conf_threshold`
10. Insert full `attempt_score_detail`
11. Update `session_prompt_attempt`:
    - `result`
    - `accuracy_score`
    - `asr_transcript`
    - `speech_detected`
    - `response_latency_sec`
12. Update `audio_file.duration_sec`
13. Upsert `patient_task_progress`
14. Upsert `session_emotion_summary`
15. If `review_recommended = true`, insert `therapist_notification`
16. Publish WS payload

### 5.6 Adaptive progression aligned to v2

Target `patient_task_progress` logic:

1. Resolve task by `prompt -> task_level -> task`
2. Find or create `patient_task_progress(patient_id, task_id)`
3. Update:
   - `current_level_id`
   - `consecutive_passes`
   - `consecutive_fails`
   - `overall_accuracy`
   - `last_final_score`
   - `total_attempts`
   - `sessions_at_level`
   - `last_attempted_at`
4. Honor:
   - `adaptive_advance_threshold`
   - `adaptive_stay_min`
   - `adaptive_stay_max`
   - `adaptive_drop_threshold`
   - `adaptive_consecutive_fail_limit`
   - `adaptive_advance_lookback_count`
   - `adaptive_advance_lookback_threshold`
   - `adaptive_consecutive_fail_ceiling`
   - `level_locked_until`

Recommended practical rule:

- Keep progression updates inside the Celery transaction so scoring and adaptive state stay consistent

### 5.7 Session emotion summary aligned to v2

Target update per attempt:

1. Aggregate all `attempt_score_detail` rows under the session
2. Write or update one `session_emotion_summary` row:
   - `session_date`
   - `dominant_emotion`
   - `avg_frustration`
   - `avg_engagement`
   - `drop_count`

This gives the progress dashboard a stable session-level summary table instead of recalculating everything from attempts only.

---

## 6. Concrete File-Level Implementation Plan

### Step 1. Fix the scoring pipeline first

Files:

- `server/app/tasks/analysis.py`
- `server/app/scoring/engine.py`

Required changes:

- Remove all joins to `prompt_scoring` and `speech_target`
- Read merged prompt columns directly from `prompt`
- Load `adaptive_threshold`, `defect_pa_threshold`, and `emotion_weights_config`
- Return and persist `rl_seconds`
- Use `rule_low_conf_threshold` rather than a hardcoded confidence cutoff
- Upsert `patient_task_progress`
- Upsert `session_emotion_summary`
- Update `audio_file.duration_sec`
- Create `therapist_notification` when review is recommended

### Step 2. Fix session upload persistence

File:

- `server/app/routers/session.py`

Required changes:

- Create `audio_file` row on upload
- Store `response_latency_sec`
- Optionally set `accuracy_score` after scoring result comes back

### Step 3. Fix baseline modeling

File:

- `server/app/routers/baseline.py`

Required changes:

- Stop flattening multiple assessments into one synthetic merged baseline
- Return real `baseline_assessment -> baseline_section -> baseline_item`
- Remove patient self-rating from the baseline flow entirely
- Return only ML-scoreable items in the patient baseline endpoints
- Exclude `clinician_rated` items from patient self-service
- Add baseline session start / attempt / complete flow mirroring therapy sessions
- Submit and persist ML results per item rather than user-entered item scores
- Use `date.today()` rather than ISO string for `assessed_on`
- Introduce scoring based on `baseline_item.formula_mode`
- Add clinician-note handling into `baseline_item_result.clinician_note`
- Aggregate `patient_baseline_result` from ML-scored `baseline_item_result` rows only

### Step 4. Add plan history and plan events

Files:

- `server/app/services/plan_generator.py`
- `server/app/routers/plans.py`

Required changes:

- Insert `plan_revision_history` on generate/add/move/delete/approve/regenerate
- Persist `clinical_rationale` when available

### Step 5. Add therapist notification lifecycle

Files:

- `server/app/routers/auth.py`
- `server/app/routers/therapist.py`
- `server/app/tasks/analysis.py`

Required changes:

- Create notification when a patient registers
- Mark or create events for patient approval
- Create `review_flagged` notifications for low-confidence attempts

### Step 6. Tighten progress semantics

Files:

- `server/app/routers/patient.py`
- `server/app/routers/progress.py`

Required changes:

- Use `patient_task_progress` as the authoritative current level source once the worker writes it
- Keep baseline severity only as initial fallback
- Prefer `session_emotion_summary` for session-level emotion reporting

---

## 7. Recommended Execution Order

Implement in this order:

1. `analysis.py` schema migration from old joins to consolidated `prompt`
2. `engine.py` expansion for thresholds, low-confidence, and adaptive updates
3. `session.py` audio tracking and latency persistence
4. `patient_task_progress` upsert logic
5. `session_emotion_summary` upsert logic
6. `therapist_notification` flagged-review logic
7. baseline API redesign with ML-only scoring
8. `plan_revision_history` integration

Reason:

- The scoring pipeline is the only truly broken old-schema dependency
- Progression, emotion summaries, and notifications all depend on that pipeline
- Baseline ML integration and plan auditing can come next once runtime scoring is stable

---

## 8. Practical Conclusion

The backend is not fully broken, but it is split between:

- a database model layer that reflects schema v2
- a runtime logic layer that still partly behaves like schema v1

The current backend works today for:

- auth
- therapist approval
- simple baseline self-rating
  - but this should be removed
- plan generation
- session upload
- WebSocket score delivery

The current backend does not yet truly implement database v2 for:

- consolidated prompt-driven scoring
- adaptive thresholds
- defect-specific PA thresholds
- emotion weight configs
- patient task progression
- session emotion summaries
- audio file lifecycle
- therapist notifications
- plan revision history
- clinically correct baseline scoring
- ML-only baseline scoring

The most important implementation task is to rewrite the Celery scoring flow around the current v2 tables. Once that is done, the rest of the database design becomes usable by the runtime.
