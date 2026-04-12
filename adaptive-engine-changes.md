# Adaptive Engine Enhancement — Design Document

## Understanding Summary

- **What**: Enhanced in-session adaptive difficulty engine with escalation, week-over-week progression, and auto plan regeneration
- **Why**: Current engine degrades one exercise in isolation with no intervention ceiling, no escalation path, and no link between within-session failures and next-week plan difficulty
- **Who**: Patients (appropriate difficulty + locked state on escalation); Therapists (actionable notifications + draft plan approval)
- **Key constraints**: 2 adaptive interventions per task session (resets weekly); full-day pause on escalation; plan regeneration requires therapist approval before patient resumes
- **Non-goals**: No scoring formula changes; no new therapist UI beyond notifications; no baseline flow changes

---

## Assumptions

1. `session.session_notes` (existing JSON blob) carries four new fields: `adaptive_interventions`, `attempted_prompt_ids`, `escalated`, `escalation_level`
2. `plan_task_assignment` gets a new `initial_level_name` VARCHAR column populated at plan generation time
3. Plan regeneration is dispatched as a new Celery task (`regenerate_plan_after_escalation`) using psycopg2 — consistent with the existing worker pattern
4. Therapist plan approval UI already exists — no new UI needed beyond the new notification types
5. Week-over-week level resolution runs lazily inside `_resolve_task_level_name` on first exercise fetch of the new week
6. The full-day pause is enforced by a new `any_escalated` boolean in the `GET /patient/tasks` response AND by hard 403 guards in the session endpoints
7. Session note parsing/serialization lives in one shared utility — not duplicated across `patient.py`, `session.py`, and `analysis.py`
8. Week-over-week averaging uses the terminal outcome per prompt (last attempt per prompt_id), not every raw attempt

---

## Schema Changes

### 1. `plan_task_assignment.initial_level_name` (new column)

```sql
ALTER TABLE plan_task_assignment ADD COLUMN initial_level_name VARCHAR;
```

Populated in `generate_weekly_plan` with the resolved `baseline_level` for every `PlanTaskAssignment` created. Used by week-over-week logic as the floor — if `initial_level_name = "beginner"`, the patient cannot degrade below beginner for that task regardless of score.

### 2. `session.session_notes` — four new fields

Initialized to defaults when a session is created. All existing reads/writes are updated to handle these keys.

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `adaptive_interventions` | int | 0 | How many times the engine has fired this session (cap: 2) |
| `attempted_prompt_ids` | list[str] | [] | Every prompt attempted this session — used for beginner rotation |
| `escalated` | bool | false | Whether this task session is locked |
| `escalation_level` | str\|null | null | Level the patient was at when escalation triggered |

---

## Component Changes

### `server/app/utils/session_notes.py` (new shared utility)

Single source of truth for all session_notes logic. Imported by `patient.py`, `session.py`, `analysis.py`, and `plan_regeneration.py`.

```python
def default_session_notes(assignment_id=None, task_id=None) -> dict:
    return {
        "assignment_id": assignment_id,
        "task_id": task_id,
        "completed_prompt_ids": [],
        "passed_prompt_ids": [],
        "completed": False,
        "completion_status": None,
        # adaptive engine fields
        "adaptive_interventions": 0,
        "attempted_prompt_ids": [],
        "escalated": False,
        "escalation_level": None,
    }

def parse_session_notes(raw: str | None) -> dict:
    # safe JSON parse, merge with defaults, normalize list fields

def serialize_session_notes(notes: dict) -> str:
    # JSON dump with normalized fields
```

All four existing locations that currently define or copy `_default_session_notes` / `_parse_session_notes` / `_serialize_session_notes` are replaced with imports from this module.

### `server/app/services/plan_generator.py`

- Populate `initial_level_name = baseline_level` on every `PlanTaskAssignment` created
- No other changes

### `server/app/tasks/analysis.py`

**Three new helpers:**

`_read_session_notes(cur, session_id) -> dict`
Reads and parses session_notes. Returns defaults if missing or malformed.

`_write_session_notes(cur, session_id, notes: dict) -> None`
Serializes and writes back to `session.session_notes`.

`_get_task_name(cur, task_id) -> str`
Single `SELECT name FROM task WHERE task_id = %s` — called only when `attempt_number == 3 and pass_fail == "fail"`.

**`attempted_prompt_ids` update** — happens on every scored attempt (pass or fail) so beginner rotation excludes prompts already seen this session.

**Adaptive logic block** — inserted after the existing `_mark_prompt_terminal` call, triggered only when `attempt_number == 3 and pass_fail == "fail"`:

```
1. Read session_notes
2. Fetch task_name via _get_task_name

3. If notes["escalated"] == true:
       Republish WS payload with adaptive_decision="escalated" and return early
       (Celery retry guard — prevents double-escalation on worker retry)

4. If adaptive_interventions >= 2:
       Set escalated=true, escalation_level=current_level_name
       Write session_notes
       Create therapist_notification type="task_escalated"
       Dispatch regenerate_plan_after_escalation.delay(patient_id, therapist_id, current_level_name)
       Publish WS payload with adaptive_decision="escalated"
       Return

5. Else (interventions < 2):
       If current level is beginner:
           candidates = beginner prompts for task NOT in attempted_prompt_ids
           If no candidates:
               Force escalation (go to step 4 with adaptive_interventions set to 2)
           Else:
               No level change — serve alternate beginner prompt
               adaptive_decision = "alternate_prompt"
       Else:
           Drop level one step via _upsert_patient_task_progress (existing "drop" logic)
           adaptive_decision = "drop"

       Increment adaptive_interventions by 1
       Write session_notes
       Create therapist_notification type="task_attempt_failed"
       Publish WS payload
```

### `server/app/routers/patient.py`

**`_default_session_notes` / `_parse_session_notes` / `_serialize_session_notes`** — removed. Replaced with imports from `server/app/utils/session_notes.py`.

**`_build_task_state`** — signature gains `initial_level_name: str`. Escalation gate added before existing prompt-loading logic:

```
If notes["escalated"] == true:
    Return TaskExerciseStateOut(
        task_complete=False,
        current_prompt=None,
        escalated=True,
        escalation_message="Your therapist is reviewing this task."
    )
```

Call site (`get_task_session_state`) passes `assignment.initial_level_name` into `_build_task_state`, which in turn passes it to `_resolve_task_level_name`.

**`GET /patient/tasks`** — response shape changes from `list[TaskAssignmentOut]` to `TodayTasksResponse`:

```python
class TodayTasksResponse(BaseModel):
    assignments: list[TaskAssignmentOut]
    any_escalated: bool
```

Server-side: for each of today's assignments, find its active session (if any) and check `escalated` in session_notes. If any is `true`, `any_escalated=True`.

Client updated to read `.assignments` instead of the raw array.

**`_resolve_task_level_name`** — gains `initial_level_name: str` parameter. Week-over-week logic:

```
1. If no patient_task_progress row exists:
       First time doing this task → use baseline level (existing behavior, unchanged)

2. If progress exists and last_attempted_at is within the current ISO week:
       Use current_level_id as-is (mid-week, no recalculation)

3. If last_attempted_at is from a prior week:
       a. Find the most recent completed session for this task (via session_prompt_attempt
          → task_level → task_id JOIN, ordered by session_date DESC)
       b. For each unique prompt_id in that session, select the attempt with
          MAX(attempt_number) → fetch its attempt_score_detail.final_score
          (terminal outcome per prompt — retries are not double-counted)
       c. Compute average_score = mean of those terminal final_scores
       d. Apply engine thresholds:
              average_score >= 75  → advance one level
              60 <= score < 75     → stay at current level
              score < 60           → drop one level
       e. Floor clamp: never drop below initial_level_name (passed in from assignment)
       f. Update patient_task_progress.current_level_id with resolved level
       g. Return resolved level name
```

### `server/app/routers/session.py`

**`POST /session/start`** — escalation hard stop added before session creation:

```
Query today's active sessions for this patient (session_type='therapy', session_date=today).
For each, parse session_notes.
If any session has escalated=true → raise HTTPException(403, "Session locked pending therapist review")
```

**`POST /session/{session_id}/attempt`** — escalation hard stop added after session load:

```
After: session = await db.get(Session, session_id)
Add:   notes = parse_session_notes(session.session_notes)
       if notes["escalated"]:
           raise HTTPException(403, "This session is locked pending therapist review")
```

These two guards ensure the lock is enforced at the API layer regardless of what the client sends.

### `server/app/tasks/plan_regeneration.py` (new file)

```python
@celery_app.task(
    name="app.tasks.plan_regeneration.regenerate_plan_after_escalation",
    bind=True,
    max_retries=2
)
def regenerate_plan_after_escalation(self, patient_id, therapist_id, escalation_level_name):
```

**Flow:**

```
1. Resolve new plan level (one step down, beginner floor):
       "advanced"     → "intermediate"
       "intermediate" → "beginner"
       "beginner"     → "beginner"

2. Archive current approved plan:
       UPDATE therapy_plan SET status='archived'
       WHERE patient_id=? AND status='approved'
       (Safe if no approved plan found — proceed regardless)

3. Generate new draft plan via raw psycopg2:
       Fetch defect_ids from patient
       Fetch task_ids from task_defect_mapping for those defects
       Fetch eligible task_ids at new_level from task_level
       Fallback to "beginner" if no tasks exist at new_level
       INSERT therapy_plan (status='draft', plan_name includes level name)
       INSERT plan_task_assignment rows (up to 14, day slots)
           → initial_level_name = new_level on each row
       INSERT plan_revision_history
           (action='auto_regenerated_after_escalation')

4. Create therapist_notification type="plan_regenerated_pending_approval":
       message: "A new {level} plan has been auto-generated for {patient_name}
                 following task escalation. Awaiting your approval."

5. Publish Redis event to ws:therapist:{therapist_id} if channel exists
```

**Error handling:**
- No tasks at degraded level → fall back to `"beginner"`, log warning, continue
- Archive step finds no approved plan → proceeds with new draft (idempotent)
- Celery retry on exception — archive step re-checks `status='approved'` guard

---

## Notification Types

| Type | Fired from | Message content |
|------|-----------|---------|
| `review_flagged` | `analysis.py` | Unchanged — low ASR confidence only |
| `task_attempt_failed` | `analysis.py` | task_name, final_score, intervention number applied |
| `task_escalated` | `analysis.py` | task_name, final_score, level the new plan will use |
| `plan_regenerated_pending_approval` | `plan_regeneration.py` | patient_name, new_level, new plan_id |

---

## WebSocket Payload — New `adaptive_decision` Values

| Value | Meaning |
|-------|---------|
| `alternate_prompt` | At beginner — a different beginner prompt will be served next |
| `escalated` | Task locked — patient will see the therapist review message |

---

## Client Changes

**`client/app/patient/tasks/[assignmentId]/page.tsx`**

- Handle `adaptive_decision="escalated"` from WS/poll → redirect to tasks list with toast: "This task has been escalated for therapist review."
- Handle `adaptive_decision="alternate_prompt"` → show "Difficulty adjusted — trying a different exercise" before advancing

**`client/app/patient/tasks/page.tsx`**

- `GET /patient/tasks` now returns `{ assignments: TaskAssignmentOut[], any_escalated: boolean }` — update all reads from raw array to `.assignments`
- If `any_escalated=true` → render full-day locked state: "One of today's tasks requires therapist review before you can continue."

**`client/lib/api.ts` or `client/types.ts`**

- Add `TodayTasksResponse` type: `{ assignments: TaskAssignmentOut[], any_escalated: boolean }`
- Add `escalated?: boolean` and `escalation_message?: string` to `TaskExerciseState`

---

## Edge Cases

| Case | Handling |
|------|---------|
| Beginner pool exhausted before 2 interventions | Treated as immediate escalation regardless of counter value |
| Task has only 1 exercise | 2-intervention limit still applies — each intervention serves one replacement |
| Celery retry after escalation already committed | Guard: `if notes["escalated"]: republish WS and return` |
| Therapist approves new plan before patient resumes | `_get_current_plan` fetches `status='approved'` newest first — new plan picked up naturally |
| Patient did same task multiple times in one week | Week-over-week uses session with most recent `session_date` for that task |
| Week-over-week score would upgrade beyond starting level | No ceiling on upgrade — `initial_level_name` is a degradation floor only |
| No tasks exist at degraded level for plan regeneration | Fall back to beginner, log warning, proceed with draft |

---

## Decision Log

| Decision | Alternatives Considered | Why This |
|----------|------------------------|----------|
| Adaptive state in `session_notes` | New `task_session_state` table | Established pattern; avoids extra table and join on every exercise fetch |
| Plan regeneration as separate Celery task | Inline in `analyze_attempt`; async service call | Clean failure domain — plan regeneration failure does not retry the scoring job |
| `initial_level_name` on `plan_task_assignment` | Derive from `therapy_plan.goals`; store in `patient_task_progress` | Assignment is the correct scope — each assignment has exactly one initial level |
| Floor passed as parameter into `_resolve_task_level_name` | Store floor on `PatientTaskProgress` | Avoids stale-floor problem if a new plan assigns the same task at a different level |
| Week-over-week resolution inside `_resolve_task_level_name` | Separate background job; compute at plan generation time | Lazy evaluation on first exercise fetch — no cron job needed, always fresh |
| Week-over-week averages terminal outcome per prompt | Average every raw attempt score | Retries would over-weight failures; terminal outcome reflects actual performance |
| Full-day pause: `any_escalated` in `GET /patient/tasks` + 403 guards in session endpoints | Client-only flag | Client flag alone is not a hard stop — direct API calls could bypass it |
| `/patient/tasks` wrapped in `TodayTasksResponse` envelope | Add field to existing `TaskAssignmentOut` | `any_escalated` is session-aggregate data, not per-assignment data — wrong shape if embedded in each row |
| Session notes in one shared utility | Keep copies in each router/task | Four locations were already diverging; new fields would create four more divergence points |
| Beginner pool exhaustion triggers early escalation | Keep retrying same prompt | No therapeutic value in repeating an already-failed prompt with no available alternatives |
| Escalation retry guard via `notes["escalated"]` check | Celery idempotency key in Redis | Simpler — single DB read, no distributed lock needed |
