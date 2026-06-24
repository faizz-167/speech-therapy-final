# Backend Flow

All routes are defined in `server/app/routers/`. FastAPI mounts them in `main.py`.

---

## API Reference

### Auth — `/auth`

#### `POST /auth/register/therapist`
Creates a therapist account.
- Generates a unique `therapist_code` (8 chars)
- Hashes password with bcrypt
- Returns JWT token + user info

#### `POST /auth/register/patient`
Creates a patient account.
- Requires a valid `therapist_code` in request body
- Status defaults to `pending` (cannot login until approved)
- Sends `patient_registered` notification to the therapist

#### `POST /auth/login`
Authenticates a user.
- Checks email/password
- For patients: rejects if `status != "approved"`
- Returns JWT token valid for 7 days

#### `GET /auth/me`
Returns the current user's profile (decoded from JWT).

---

### Therapist — `/therapist`

#### `GET /therapist/profile`
Returns therapist info.

#### `GET /therapist/dashboard`
Returns:
- Total/approved/pending patient counts
- Patients missing a baseline assessment
- Patients missing an approved plan
- Unread notification count

#### `GET /therapist/patients`
Lists all patients assigned to this therapist, with status.

#### `GET /therapist/patients/{patient_id}`
Single patient detail: demographics, defects, baseline status, plan status.

#### `POST /therapist/patients/{patient_id}/approve`
Approves a pending patient.
- Sets status → `approved`
- Assigns `defect_ids`, `primary_diagnosis`, `clinical_notes`
- Sends `therapist_approved` notification to patient

#### `POST /therapist/patients/{patient_id}/reject`
Deletes the patient record (permanent).

#### `GET /therapist/notifications`
Lists therapist notifications, newest first.

#### `POST /therapist/notifications/read-all`
Marks all as read.

#### `POST /therapist/notifications/{id}/read`
Marks one notification as read.

#### `GET /therapist/defects`
Returns full list of defect categories (for the approval form).

#### `GET /therapist/patients/{patient_id}/adaptation-activity`
Returns escalation events and any auto-regenerated plans for this patient.

---

### Patient — `/patient`

#### `GET /patient/profile`
Returns patient info including:
- Assigned defects
- Therapist name
- `current_streak` and `longest_streak` (computed from session activity dates)

#### `GET /patient/home`
Quick status check:
- Has the patient completed a baseline?
- How many tasks are scheduled today?
- Is there an approved plan?

#### `GET /patient/tasks`
Today's task assignments from the active approved plan (filtered by day_index = today's weekday).

#### `GET /patient/tasks/{assignment_id}/prompts`
Returns prompts at the current level for this assignment.
- Level is pulled from `patient_task_progress.current_level_id`
- Defaults to `initial_level_name` if no progress exists

#### `GET /patient/tasks/{assignment_id}/session-state`
Returns the adaptive session queue state: which prompts are queued, which have been attempted, the current level, etc.

#### `POST /patient/tasks/{assignment_id}/complete`
Marks an assignment as `completed`.

#### `GET /patient/notifications`
Patient notifications list.

#### `POST /patient/notifications/read-all`
Marks all as read.

---

### Baseline — `/baseline`

#### `GET /baseline/exercises`
Returns a filtered set of baseline items (max 7) for the patient's assigned defects.
- Looks up `baseline_defect_mapping` to find relevant assessments
- Returns items from relevant `baseline_section` rows

#### `POST /baseline/start`
Creates a `session` with `session_type = "baseline"`.
Returns the `session_id` for subsequent uploads.

#### `POST /baseline/{session_id}/attempt`
Accepts a multipart audio file upload.
- Saves file to `UPLOAD_DIR`
- Creates a `baseline_attempt` row with `result = "pending"`
- Triggers Celery task: `baseline_analysis.score_baseline_attempt`
- Returns `{ attempt_id }` for polling

#### `GET /baseline/attempt/{attempt_id}`
Polls the baseline attempt status.
- Returns `result: pending | scored | failed`
- On `scored`: returns all ML metrics

#### `POST /baseline/{session_id}/complete`
Aggregates item-level scores into a `patient_baseline_result`.
- Calculates severity_rating from percentile
- Creates `baseline_item_result` rows

#### `GET /baseline/result`
Returns the patient's most recent baseline result.

#### `GET /baseline/therapist-view/{patient_id}`
Therapist view of a patient's baseline summary.

#### `GET /baseline/therapist-view/{patient_id}/items`
Item-level breakdown for therapist review.

---

### Plans — `/plans`

#### `POST /plans/generate`
Generates a new therapy plan.
- Input: `patient_id`, optional task selections, start/end dates
- Logic in `services/plan_generator.py`:
  1. Fetches patient's assigned defect IDs
  2. Queries `task_defect_mapping` to find relevant tasks
  3. Distributes tasks across 7 days (day_index 0–6) by priority
  4. Creates `therapy_plan` (status = `draft`)
  5. Creates `plan_task_assignment` rows

#### `GET /plans/{plan_id}`
Returns plan with all assignments, task details, and current status.

#### `POST /plans/{plan_id}/approve`
Approves a draft plan.
- Sets status → `approved`
- Sends `plan_updated` notification to patient
- Logs revision with action = `approved`

#### `POST /plans/{plan_id}/add-task`
Adds an assignment to an existing plan.
- Logs revision with action = `add_task`

#### `PUT /plans/{plan_id}/assignments/{assignment_id}`
Updates an assignment (change level, reorder within day).
- Logs revision

#### `DELETE /plans/{plan_id}/assignments/{assignment_id}`
Removes an assignment.
- Logs revision with action = `remove_task`

#### `GET /plans/{plan_id}/revisions`
Returns the full audit trail for this plan.

---

### Session — `/session`

#### `POST /session/start`
Starts or resumes a therapy session.
- Validates assignment exists and belongs to patient's plan
- Checks `plan_lock.patient_has_pending_plan_review()` — blocks if locked
- Creates `session` row or returns existing open session
- Initializes `session_notes` JSON with prompt queue

#### `POST /session/{session_id}/attempt`
Accepts audio upload for a therapy attempt.
- Validates: session is open, assignment not locked, attempt_number ≤ 3
- Saves audio file
- Creates `session_prompt_attempt` with `result = "pending"`
- Triggers Celery task: `analysis.score_therapy_attempt`
- Returns `{ attempt_id }`

#### `GET /session/attempt/{attempt_id}`
Polls therapy attempt status.
- On `scored`: returns full `attempt_score_detail`

#### `GET /session/{session_id}`
Returns session metadata and current state.

---

### Progress — Root Level

#### `GET /patient/progress`
Patient's own progress overview:
- Task-level accuracy trends
- Emotion history
- Streak data
- Week-by-week comparison

#### `GET /therapist/patients/{patient_id}/progress`
Therapist view of a patient's progress.
- Same data + ability to see all sessions

---

## Key Business Logic Flows

### Therapist Approves a Patient

```
POST /therapist/patients/{id}/approve
  └─ Validate: patient exists, is pending, belongs to this therapist
  └─ Set patient.status = "approved"
  └─ Set patient.pre_assigned_defect_ids = { defect_ids: [...] }
  └─ Set patient.primary_diagnosis, clinical_notes
  └─ Create patient_notification: type = "therapist_approved"
  └─ Return updated patient
```

---

### Therapist Generates a Plan

```
POST /plans/generate
  └─ Fetch patient.pre_assigned_defect_ids
  └─ Query task_defect_mapping WHERE defect_id IN [patient defects]
  └─ Sort tasks by relevance_level (primary first)
  └─ Distribute N tasks across 7 days in round-robin by priority
  └─ Create therapy_plan (status = draft)
  └─ For each task:
       Create plan_task_assignment (day_index, priority_order, initial_level_name)
  └─ Return plan_id
```

---

### Patient Starts a Therapy Session

```
POST /session/start { assignment_id }
  └─ Fetch assignment → validate belongs to patient's approved plan
  └─ Check plan_lock: if escalated and not reviewed → 403 Locked
  └─ Find or create open session for today
  └─ Fetch patient_task_progress for this task
       If none: create with current_level = initial_level_name
  └─ Fetch prompts at current_level
  └─ Build queue_items from prompts
  └─ Initialize session_notes JSON
  └─ Return { session_id, queue_items, current_level }
```

---

### Patient Submits an Audio Attempt

```
POST /session/{session_id}/attempt (multipart audio)
  └─ Validate session is open
  └─ Validate attempt_number <= 3
  └─ Save audio to UPLOAD_DIR/{patient_id}/{filename}
  └─ Create session_prompt_attempt { result: "pending" }
  └─ Enqueue Celery task: score_therapy_attempt(attempt_id, config)
  └─ Return { attempt_id, status: "pending" }

[Client polls GET /session/attempt/{attempt_id}]

Celery task: score_therapy_attempt
  └─ Load attempt, prompt, task, scoring weights, emotion config
  └─ Run ML pipeline (see ml-pipeline.md)
  └─ Compute final_score
  └─ Determine adaptive_decision (advance / stay / drop)
  └─ Write attempt_score_detail
  └─ Call attempt_persistence:
       └─ Update patient_task_progress
       └─ Update session_notes queue state
       └─ Check escalation trigger
       └─ Publish to Redis → WebSocket delivers to patient
```

---

### Adaptive Escalation Flow

```
Celery: score_therapy_attempt
  └─ adaptive_decision = "drop" for 2nd time in this session?
       └─ SET session_notes.escalated = true
       └─ SET session_notes.adaptive_interventions += 1
       └─ Lock plan_task_assignment.paused = true
       └─ Trigger plan_regeneration.regenerate_plan_after_escalation(patient_id)
            └─ Create new therapy_plan (status = draft)
            └─ Copy assignments with adjusted difficulty levels
            └─ Log revision: action = "auto_regenerated_after_escalation"
            └─ Create therapist_notification: type = "plan_regenerated"
            └─ Create patient_notification: type = "plan_updated"
```

---

### Streak Calculation

Runs on `GET /patient/profile`:

```python
# Fetch all distinct UTC dates where patient had at least one session
activity_dates = SELECT DISTINCT DATE(session_date) FROM session
                 WHERE patient_id = ? ORDER BY date DESC

current_streak = 0
today = utc_today()
date_cursor = today

for date in activity_dates:
    if date == date_cursor:
        current_streak += 1
        date_cursor -= 1 day
    else:
        break

longest_streak = max(patient.longest_streak, current_streak)
```

---

## Middleware & Dependencies

### Authentication Dependencies

```python
# Injected into protected routes via FastAPI Depends()
get_current_therapist() → Therapist  # decodes JWT, checks role="therapist"
get_current_patient()   → Patient    # decodes JWT, checks role="patient"
get_db()                → AsyncSession  # yields DB session
```

### CORS

Configured in `main.py`. Allowed origins from `CORS_ORIGINS` env var (default: `localhost:3000`).

### WebSocket

```python
# main.py
@app.websocket("/ws/{patient_id}")
async def websocket_endpoint(ws, patient_id):
    await ws.accept()
    redis = await aioredis.from_url(REDIS_URL)
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"patient:{patient_id}")
    async for message in pubsub.listen():
        await ws.send_text(message["data"])
```

### Startup

```python
# main.py lifespan event
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

All SQLAlchemy models are imported before this runs so all tables are created on first boot.
