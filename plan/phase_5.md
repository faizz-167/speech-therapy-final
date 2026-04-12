# Phase 5 — Patient Router Updates

## Objective
Three coordinated changes to `server/app/routers/patient.py` and `server/app/schemas/patient.py`:
1. Add escalation gate to `_build_task_state` (returns early if task is locked).
2. Add week-over-week level progression logic to `_resolve_task_level_name`.
3. Change `GET /patient/tasks` response from a raw list to a `TodayTasksResponse` envelope that includes `any_escalated`.

## Dependencies
- Phase 1 COMPLETED (session_notes utility must replace local helpers before this phase modifies the function signatures).
- Phase 2 COMPLETED (`initial_level_name` on `PlanTaskAssignment` must exist to be passed into the resolver).

## Subtasks

### 5.1 — Add `TodayTasksResponse` schema to `schemas/patient.py`
File: `server/app/schemas/patient.py`

```python
class TodayTasksResponse(BaseModel):
    assignments: list[TaskAssignmentOut]
    any_escalated: bool
```

### 5.2 — Update `TaskExerciseStateOut` schema
File: `server/app/schemas/patient.py`

Add two optional fields to `TaskExerciseStateOut`:
```python
class TaskExerciseStateOut(BaseModel):
    session_id: str
    current_level: str
    total_prompts: int
    completed_prompts: int
    task_complete: bool
    current_prompt: Optional[PromptOut]
    escalated: bool = False                          # NEW
    escalation_message: Optional[str] = None         # NEW
```

### 5.3 — Update `_resolve_task_level_name` signature
File: `server/app/routers/patient.py`

Change signature from:
```python
async def _resolve_task_level_name(db, patient_id, task_id) -> str:
```
To:
```python
async def _resolve_task_level_name(db, patient_id, task_id, initial_level_name: str | None = None) -> str:
```

### 5.4 — Implement week-over-week logic in `_resolve_task_level_name`
After the existing `patient_task_progress` row lookup, add the following branching logic. The current code falls back to baseline if no progress row exists — keep that unchanged and only add new logic for the "prior week" case.

```
Current logic:
  1. If no patient_task_progress row → use baseline level (unchanged)
  2. If progress row exists → use current_level_id (unchanged for mid-week)

NEW logic — insert between step 1 and the current "use current_level_id" return:

  2a. If progress row exists AND last_attempted_at is in the current ISO week:
          → use current_level_id as-is (no recalculation) [existing behavior]

  2b. If progress row exists AND last_attempted_at is from a PRIOR ISO week:
          a. Find the most recent completed session for this (patient, task):
             SELECT s.session_id, s.session_date
             FROM session s
             JOIN session_prompt_attempt spa ON spa.session_id = s.session_id
             JOIN prompt p ON p.prompt_id = spa.prompt_id
             JOIN task_level tl ON tl.level_id = p.task_level_id
             WHERE s.patient_id = :patient_id
               AND tl.task_id = :task_id
               AND s.session_type = 'therapy'
             ORDER BY s.session_date DESC
             LIMIT 1

          b. For each unique prompt_id in that session, get the terminal final_score
             (MAX attempt_number per prompt):
             SELECT spa.prompt_id, asd.final_score
             FROM session_prompt_attempt spa
             JOIN attempt_score_detail asd ON asd.attempt_id = spa.attempt_id
             WHERE spa.session_id = :session_id
               AND spa.attempt_number = (
                   SELECT MAX(spa2.attempt_number)
                   FROM session_prompt_attempt spa2
                   WHERE spa2.session_id = :session_id
                     AND spa2.prompt_id = spa.prompt_id
               )

          c. average_score = mean(final_scores) — if empty, stay at current level

          d. Resolve new level name:
             if average_score >= 75   → advance one step (beg→int, int→adv, adv→adv)
             elif average_score >= 60 → stay at current level
             else                     → drop one step (adv→int, int→beg, beg→beg)

          e. Floor clamp:
             if resolved_level is "below" initial_level_name:
                 resolved_level = initial_level_name
             (Level order: beginner < intermediate < advanced)

          f. Update patient_task_progress.current_level_id with the resolved level_id:
             SELECT level_id FROM task_level WHERE task_id = :task_id AND level_name = :resolved_level
             UPDATE patient_task_progress SET current_level_id = :level_id WHERE progress_id = :progress_id

          g. Return resolved_level name
```

**ISO week check:**
```python
from datetime import date
def _same_iso_week(dt: datetime, today: date) -> bool:
    return dt.isocalendar()[:2] == today.isocalendar()[:2]
```

**Level advance map:**
```python
LEVEL_ADVANCE = {"beginner": "intermediate", "intermediate": "advanced", "advanced": "advanced"}
LEVEL_DROP    = {"advanced": "intermediate", "intermediate": "beginner", "beginner": "beginner"}
LEVEL_ORDER   = {"beginner": 0, "intermediate": 1, "advanced": 2}
```

### 5.5 — Update `_build_task_state` — escalation gate
File: `server/app/routers/patient.py`

At the top of `_build_task_state`, before any prompt-loading logic:
```python
notes = parse_session_notes(session.session_notes)
if notes.get("escalated"):
    return TaskExerciseStateOut(
        session_id=str(session.session_id),
        current_level=current_level or "",
        total_prompts=0,
        completed_prompts=0,
        task_complete=False,
        current_prompt=None,
        escalated=True,
        escalation_message="Your therapist is reviewing this task. Please check back later.",
    )
```

The `session` object must be in scope — read it from the DB or pass it in. Inspect the current `_build_task_state` signature to determine the cleanest way to make `session` available (it's likely already fetched in the caller `get_task_session_state`).

### 5.6 — Update `_build_task_state` — pass `initial_level_name` to resolver
Modify the call to `_resolve_task_level_name` inside `_build_task_state` (or its caller):
```python
level_name = await _resolve_task_level_name(
    db, patient_id, task_id,
    initial_level_name=assignment.initial_level_name
)
```
The `assignment` object is already fetched in `get_task_session_state`. Pass it into `_build_task_state` or access it in the calling scope. Choose the approach that requires the least restructuring.

### 5.7 — Update `GET /patient/tasks` to return `TodayTasksResponse`
File: `server/app/routers/patient.py`

Current return type: `list[TaskAssignmentOut]`
New return type: `TodayTasksResponse`

**Algorithm:**
1. Build the `assignments` list as before.
2. For each assignment in today's assignments, check if there is an active (non-completed) session:
   ```sql
   SELECT session_notes FROM session
   WHERE patient_id = :patient_id
     AND plan_id = :plan_id
     AND session_type = 'therapy'
   ORDER BY session_date DESC
   LIMIT 1
   ```
   Parse session_notes. If `escalated == True` for any assignment → `any_escalated = True`.
3. Return:
   ```python
   return TodayTasksResponse(assignments=assignments, any_escalated=any_escalated)
   ```

Update the response_model annotation on the route if one is set.

## Execution Plan

1. Open `server/app/schemas/patient.py`. Add `TodayTasksResponse` and update `TaskExerciseStateOut` (subtasks 5.1, 5.2).
2. Open `server/app/routers/patient.py` (read full file first — it is large).
3. Implement `_resolve_task_level_name` changes: add `initial_level_name` parameter and week-over-week branch (subtasks 5.3, 5.4).
4. Implement `_build_task_state` escalation gate and `initial_level_name` pass-through (subtasks 5.5, 5.6).
5. Update `GET /patient/tasks` endpoint (subtask 5.7).
6. Update `status.md` after each subtask.

## Validation Criteria
- [ ] `TodayTasksResponse` schema exists in `schemas/patient.py`.
- [ ] `TaskExerciseStateOut` has `escalated: bool = False` and `escalation_message: Optional[str] = None`.
- [ ] `_resolve_task_level_name` accepts `initial_level_name` parameter.
- [ ] Week-over-week logic: prior-week progress → query terminal scores → average → threshold → floor clamp → update progress → return new level.
- [ ] Mid-week: `last_attempted_at` in current ISO week → no recalculation, returns current level.
- [ ] `_build_task_state` returns escalated response before any prompt loading when `notes["escalated"] == True`.
- [ ] `GET /patient/tasks` returns `{ assignments: [...], any_escalated: bool }` shape.
- [ ] `any_escalated=True` when at least one today's assignment has an escalated session.
