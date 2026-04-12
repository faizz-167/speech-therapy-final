# Phase 4 — Plan Regeneration Celery Task

## Objective
Create `server/app/tasks/plan_regeneration.py` — a new Celery task that fires when a patient escalates. It degrades the plan level by one step, archives the current approved plan, generates a new draft plan via raw psycopg2 (consistent with the existing worker pattern), and notifies the therapist.

## Dependencies
- Phase 2 COMPLETED (`initial_level_name` column must exist on `plan_task_assignment`).
- Phase 1 COMPLETED (utility must exist for session_notes import, though this task does not use it directly — it is needed for the import to not fail).

## Subtasks

### 4.1 — Create `server/app/tasks/plan_regeneration.py`
Create the file. Wire it to the Celery app using the same import pattern as `analysis.py`:
```python
from app.tasks.celery_app import celery_app   # or wherever celery_app is defined
import psycopg2
import uuid
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
```
Check `server/app/tasks/analysis.py` for the exact celery_app import path and psycopg2 connection pattern — replicate it exactly.

### 4.2 — Implement level degradation logic
```python
LEVEL_DEGRADATION = {
    "advanced": "intermediate",
    "intermediate": "beginner",
    "beginner": "beginner",
}

def _degrade_level(level_name: str) -> str:
    return LEVEL_DEGRADATION.get(level_name.lower(), "beginner")
```

### 4.3 — Archive current approved plan (idempotent)
```sql
UPDATE therapy_plan
SET status = 'archived'
WHERE patient_id = %s AND status = 'approved'
```
If no rows updated: log a warning and continue. Do not fail the task.

### 4.4 — Generate new draft plan via psycopg2
Full flow:
```
a. Fetch patient's defect IDs:
   pre_assigned_defect_ids is JSONB shaped {"defect_ids": ["id1", "id2", ...]}.
   Do NOT use unnest() — that is for Postgres arrays, not JSONB.
   Instead, fetch the JSONB value and parse it in Python (mirrors plan_generator.py line 32):

   cur.execute(
       "SELECT pre_assigned_defect_ids FROM patient WHERE patient_id = %s",
       (patient_id,)
   )
   row = cur.fetchone()
   defect_ids = (row[0] or {}).get("defect_ids", []) if row else []
   if not defect_ids:
       logger.warning("Patient %s has no defect_ids in pre_assigned_defect_ids", patient_id)
       raise self.retry(...)

b. Fetch task_ids mapped to those defects:
   SELECT DISTINCT task_id FROM task_defect_mapping WHERE defect_id = ANY(%s)
   Pass defect_ids as a Python list — psycopg2 converts list → ANY(%s) correctly.

c. Fetch task_ids eligible at new_level (from task_level):
   SELECT tl.task_id FROM task_level tl
   WHERE tl.task_id = ANY(%s) AND tl.level_name = %s
   (pass new_level_name as %s)

d. If no rows:
   new_level_name = "beginner"
   Re-run query c with "beginner"
   Log warning: "No tasks at degraded level — falling back to beginner"

e. Fetch therapist_id for the patient:
   SELECT assigned_therapist_id FROM patient WHERE patient_id = %s

f. Fetch patient full_name for notification message:
   SELECT full_name FROM patient WHERE patient_id = %s

g. INSERT new therapy_plan:
   INSERT INTO therapy_plan (plan_id, patient_id, therapist_id, plan_name, status, created_at)
   VALUES (%s, %s, %s, %s, 'draft', NOW())
   plan_name = f"Auto-Regenerated {new_level_name.title()} Plan"
   new_plan_id = uuid.uuid4()

h. INSERT plan_task_assignment rows (up to 14, cycling through 7-day week):
   eligible_task_ids = list from step c/d (take min(14, len))
   For i, task_id in enumerate(eligible_task_ids[:14]):
       day_index = i % 7
       priority_order = i // 7 + 1  (1 or 2 per day)
       level_id = SELECT level_id FROM task_level WHERE task_id=%s AND level_name=%s
       INSERT INTO plan_task_assignment
           (assignment_id, plan_id, task_id, therapist_id, day_index, priority_order,
            status, initial_level_name)
       VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s)
       initial_level_name = new_level_name
```

### 4.5 — Insert `plan_revision_history` row
```sql
INSERT INTO plan_revision_history
    (revision_id, plan_id, therapist_id, action, note, created_at)
VALUES
    (%s, %s, %s, 'auto_regenerated_after_escalation',
     'Plan auto-generated after patient task escalation at level: {escalation_level_name}',
     NOW())
```

### 4.6 — Create `plan_regenerated_pending_approval` notification
The `therapist_notification` table column is `type`, not `notification_type`. Use:
```sql
INSERT INTO therapist_notification
    (notification_id, therapist_id, type, patient_id, plan_id, message, is_read, created_at)
VALUES
    (%s, %s, 'plan_regenerated_pending_approval', %s, %s,
     'A new {new_level_name} plan has been auto-generated for {patient_name} following task escalation. Awaiting your approval.',
     FALSE, NOW())
```
Pass `new_plan_id` for `plan_id` so therapist UIs can deep-link to the draft plan.

### 4.7 — Publish Redis event to therapist WS channel
Check `analysis.py` for the exact Redis publish pattern. Replicate it for the therapist channel:
```python
channel = f"ws:therapist:{therapist_id}"
payload = json.dumps({
    "type": "plan_regenerated",
    "plan_id": str(new_plan_id),
    "patient_id": str(patient_id),
    "level": new_level_name,
})
# publish via redis client (same pattern as analysis.py)
```
If the channel does not exist (no active WS connection), `publish` will simply send to 0 subscribers — this is safe and expected.

## Full Task Skeleton

```python
@celery_app.task(
    name="app.tasks.plan_regeneration.regenerate_plan_after_escalation",
    bind=True,
    max_retries=2
)
def regenerate_plan_after_escalation(self, patient_id: str, therapist_id: str, escalation_level_name: str):
    conn = None
    try:
        conn = psycopg2.connect(DATABASE_URL_SYNC)  # from settings
        conn.autocommit = False
        cur = conn.cursor()

        new_level_name = _degrade_level(escalation_level_name)

        # 4.3 Archive approved plan
        cur.execute(
            "UPDATE therapy_plan SET status='archived' WHERE patient_id=%s AND status='approved'",
            (patient_id,)
        )

        # 4.4 Generate draft plan (steps a-h)
        ...

        # 4.5 Insert revision history
        ...

        conn.commit()

        # 4.6 Notification (commit first so it's durable on partial failure)
        cur.execute(...)
        conn.commit()

        # 4.7 Redis publish
        ...

    except Exception as exc:
        if conn:
            conn.rollback()
        raise self.retry(exc=exc, countdown=30)
    finally:
        if conn:
            conn.close()
```

## Execution Plan

1. Read `server/app/tasks/analysis.py` to extract: celery_app import path, psycopg2 connection string source (settings), Redis client construction pattern.
2. Create `server/app/tasks/plan_regeneration.py` implementing all subtasks 4.1–4.7 in order.
3. Verify the task name string matches what Phase 3 will use in `.delay()`.
4. Update `status.md` as each subtask completes.

## Validation Criteria
- [ ] File `server/app/tasks/plan_regeneration.py` exists.
- [ ] Task is decorated with `@celery_app.task(name="app.tasks.plan_regeneration.regenerate_plan_after_escalation", bind=True, max_retries=2)`.
- [ ] `_degrade_level("advanced")` returns `"intermediate"`, `_degrade_level("beginner")` returns `"beginner"`.
- [ ] Archive step is safe when no approved plan exists (0 rows updated → continue).
- [ ] New plan `status='draft'`, all assignments have `initial_level_name` set to new level.
- [ ] Fallback to `"beginner"` when no tasks exist at degraded level.
- [ ] `plan_revision_history` row inserted with `action='auto_regenerated_after_escalation'`.
- [ ] `plan_regenerated_pending_approval` notification inserted.
- [ ] Redis publish uses `ws:therapist:{therapist_id}` channel.
- [ ] Transaction rolls back on failure; Celery retry fires.
