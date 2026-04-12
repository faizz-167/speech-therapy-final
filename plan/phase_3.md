# Phase 3 — Analysis Task: Adaptive Intervention Engine

## Objective
Inject the full adaptive engine into `server/app/tasks/analysis.py`. This is the core behavioral change: when a patient fails a prompt on attempt 3, the engine reads the session's intervention counter, decides whether to serve an alternate beginner prompt, drop a level, or escalate, then writes the decision back to session_notes and fires the appropriate notifications.

## Dependencies
- Phase 1 COMPLETED (`session_notes` utility must exist).
- Phase 2 COMPLETED (`initial_level_name` column must exist on `plan_task_assignment`).
- Phase 4 must exist **before subtask 3.8** (the `.delay()` call requires `plan_regeneration.py` to be importable). Implement Phase 4 first or defer subtask 3.8 until Phase 4 is done.

## Subtasks

### 3.1 — Import session_notes utility in `analysis.py`
At the top of `server/app/tasks/analysis.py`, add:
```python
from app.utils.session_notes import default_session_notes, parse_session_notes, serialize_session_notes
```
Remove any inline JSON parsing of session_notes that duplicates this utility, if present.

### 3.2 — Add `_read_session_notes(cur, session_id) -> dict`
Raw psycopg2 helper (the worker uses psycopg2, not SQLAlchemy async):
```python
def _read_session_notes(cur, session_id: str) -> dict:
    cur.execute(
        "SELECT session_notes FROM session WHERE session_id = %s",
        (session_id,)
    )
    row = cur.fetchone()
    raw = row[0] if row else None
    return parse_session_notes(raw)
```

### 3.3 — Add `_write_session_notes(cur, session_id, notes: dict) -> None`
```python
def _write_session_notes(cur, session_id: str, notes: dict) -> None:
    cur.execute(
        "UPDATE session SET session_notes = %s WHERE session_id = %s",
        (serialize_session_notes(notes), session_id)
    )
```

### 3.4 — Add `_get_task_name(cur, task_id) -> str`
Called only when escalation or notification is needed:
```python
def _get_task_name(cur, task_id: str) -> str:
    cur.execute("SELECT name FROM task WHERE task_id = %s", (task_id,))
    row = cur.fetchone()
    return row[0] if row else "Unknown Task"
```

### 3.5 — Track `attempted_prompt_ids` on every scored attempt
**Location:** After `_mark_prompt_terminal` is called (or immediately after the score is written), add:

```python
notes = _read_session_notes(cur, str(session_id))
if prompt_id not in notes["attempted_prompt_ids"]:
    notes["attempted_prompt_ids"].append(prompt_id)
_write_session_notes(cur, str(session_id), notes)
```

This must run on **every** scored attempt (pass AND fail, all attempt numbers). It ensures the beginner rotation excludes prompts already seen in this session.

### 3.6 — Insert adaptive intervention block
**Trigger condition:** `attempt_number == 3 and pass_fail == "fail"`

Insert the following block immediately after `_mark_prompt_terminal` is called and the `attempted_prompt_ids` are updated. The block uses `cur` (psycopg2 cursor), `session_id`, `task_id`, `patient_id`, `therapist_id`, and `current_level_name` (the name of the level the prompt was served from — resolve this from the task_level table using the level_id on the prompt).

```
ADAPTIVE BLOCK PSEUDOCODE:

1. notes = _read_session_notes(cur, session_id)
2. task_name = _get_task_name(cur, task_id)

3. If notes["escalated"] == True:
       # Celery retry guard — escalation already committed, just republish
       Publish WS payload with adaptive_decision="escalated"
       Return early from the task

4. If notes["adaptive_interventions"] >= 2:
       # Force escalation
       notes["escalated"] = True
       notes["escalation_level"] = current_level_name
       _write_session_notes(cur, session_id, notes)
       Insert therapist_notification(
           type="task_escalated",
           patient_id=patient_id,
           therapist_id=therapist_id,
           message=f"Task '{task_name}' has been escalated after 2 failed interventions. "
                   f"Final score: {final_score:.1f}. New plan will be generated at a lower level."
       )
       Dispatch regenerate_plan_after_escalation.delay(patient_id, therapist_id, current_level_name)
       Publish WS payload with adaptive_decision="escalated"
       Return

5. Else (notes["adaptive_interventions"] < 2):
       If current_level_name == "beginner":
           # Attempt beginner prompt rotation
           cur.execute(
               "SELECT p.prompt_id FROM prompt p
                JOIN task_level tl ON p.task_level_id = tl.level_id
                WHERE tl.task_id = %s AND tl.level_name = 'beginner'",
               (task_id,)
           )
           all_beginner_prompt_ids = [row[0] for row in cur.fetchall()]
           candidates = [pid for pid in all_beginner_prompt_ids
                         if pid not in notes["attempted_prompt_ids"]]

           If not candidates:
               # Beginner pool exhausted → force escalation (go to step 4 logic)
               notes["adaptive_interventions"] = 2
               # Execute step 4 inline (same escalation block)
               ...
           Else:
               adaptive_decision = "alternate_prompt"
               # No level change — next exercise fetch will serve a new beginner prompt
               # (the attempted_prompt_ids list already excludes the failed one)
       Else:
           # Drop one level
           # current_level_id is the task_level_id on the prompt row (already loaded in analyze_attempt)
           _upsert_patient_task_progress(
               cur,
               patient_id,
               task_id,
               current_level_id,   # level_id FK, not level name
               "drop",             # adaptive_decision
               final_score,        # current attempt's final_score
               "fail",             # pass_fail
           )
           adaptive_decision = "drop"

       notes["adaptive_interventions"] += 1
       _write_session_notes(cur, session_id, notes)

       Insert therapist_notification(
           type="task_attempt_failed",
           patient_id=patient_id,
           therapist_id=therapist_id,
           message=f"Patient failed '{task_name}' (attempt 3, score {final_score:.1f}). "
                   f"Adaptive intervention {notes['adaptive_interventions']} of 2 applied: {adaptive_decision}."
       )
       Publish WS payload with adaptive_decision=adaptive_decision
```

**Implementation note on `current_level_name`:** The level name can be resolved from the prompt's `task_level_id` via:
```sql
SELECT level_name FROM task_level WHERE level_id = %s
```
Where the `level_id` is the `task_level_id` on the `prompt` row. This is already loaded in `analyze_attempt`.

### 3.7 — Wire escalation notifications
The two notification types are inserted via raw psycopg2 `INSERT INTO therapist_notification` (consistent with existing `_create_review_notification` pattern in `analysis.py`). Use the same pattern — do not call any async ORM inside the Celery worker.

Notification schema fields needed (match `therapist_notification` table exactly — column is `type`, not `notification_type`):

```python
cur.execute(
    "INSERT INTO therapist_notification"
    " (notification_id, therapist_id, type, patient_id, attempt_id, message, is_read, created_at)"
    " VALUES (%s, %s, %s, %s, %s, %s, false, NOW())",
    (str(uuid.uuid4()), therapist_id, notification_type_value, patient_id, attempt_id, message_text),
)
```

Fields:
- `notification_id`: new `uuid.uuid4()`
- `therapist_id`: therapist_id string
- `type`: `"task_attempt_failed"` or `"task_escalated"` (column name is `type`, **not** `notification_type`)
- `patient_id`: patient_id string
- `attempt_id`: attempt_id string (available in `analyze_attempt` context)
- `message`: message text
- `is_read`: false (literal in SQL)
- `created_at`: NOW() (literal in SQL)

### 3.8 — Dispatch `regenerate_plan_after_escalation.delay()`
Add import at top of `analysis.py`:
```python
from app.tasks.plan_regeneration import regenerate_plan_after_escalation
```
This import must not be added until Phase 4 is COMPLETED (the file must exist).

In the escalation branch (step 4 of the adaptive block):
```python
regenerate_plan_after_escalation.delay(
    str(patient_id),
    str(therapist_id),
    current_level_name
)
```

## Execution Plan

1. Read `server/app/tasks/analysis.py` in full (766 lines — read in chunks if needed).
2. Add import for session_notes utility (subtask 3.1).
3. Add three helper functions `_read_session_notes`, `_write_session_notes`, `_get_task_name` near the top of the file with other helpers (subtasks 3.2–3.4).
4. Locate the per-attempt scoring block. After `_mark_prompt_terminal` is called, add `attempted_prompt_ids` tracking (subtask 3.5).
5. Add the adaptive intervention block immediately after subtask 3.5 logic, gated on `attempt_number == 3 and pass_fail == "fail"` (subtask 3.6).
6. Implement notification inserts using existing psycopg2 INSERT pattern (subtask 3.7).
7. After Phase 4 is COMPLETED: add `regenerate_plan_after_escalation` import and `.delay()` call (subtask 3.8).
8. Update `status.md` as each subtask completes.

## Validation Criteria
- [ ] `_read_session_notes`, `_write_session_notes`, `_get_task_name` functions exist in `analysis.py`.
- [ ] `attempted_prompt_ids` is updated on every scored attempt (pass and fail).
- [ ] Adaptive block only fires when `attempt_number == 3 and pass_fail == "fail"`.
- [ ] Celery retry guard: if `notes["escalated"] == True` at entry, republish WS and return without double-escalating.
- [ ] Escalation fires when `adaptive_interventions >= 2`: sets `escalated=True`, writes notes, creates `task_escalated` notification, dispatches plan regen.
- [ ] Beginner rotation: if `current_level_name == "beginner"` and candidates exist → `adaptive_decision="alternate_prompt"`, no level change.
- [ ] Beginner pool exhausted → treats as escalation (same flow as `>= 2` interventions).
- [ ] Non-beginner fail → `_upsert_patient_task_progress` called with "drop", `adaptive_decision="drop"`.
- [ ] `task_attempt_failed` notification created with `type='task_attempt_failed'` and intervention count in message.
- [ ] WS payload published with correct `adaptive_decision` value in all branches.
