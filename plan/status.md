# Adaptive Engine Implementation — Status Tracker

## Legend
- `NOT_STARTED` — work not yet begun
- `IN_PROGRESS` — currently being executed
- `COMPLETED` — all subtasks done and validation passed

---

## Phase Overview

| Phase | Title | Status | Notes |
|-------|-------|--------|-------|
| 1 | Shared Session Notes Utility | NOT_STARTED | No dependencies — start here |
| 2 | Schema + Plan Generator Changes | NOT_STARTED | Depends on nothing; can run after Phase 1 |
| 3 | Analysis Task — Adaptive Engine | NOT_STARTED | Depends on Phase 1 + Phase 2 |
| 4 | Plan Regeneration Celery Task | NOT_STARTED | Depends on Phase 2 |
| 5 | Patient Router Updates | NOT_STARTED | Depends on Phase 1 + Phase 2 |
| 6 | Session Router Hard-Stop Guards | NOT_STARTED | Depends on Phase 1 |
| 7 | Client Updates | NOT_STARTED | Depends on Phase 3 + Phase 5 |

---

## Phase 1 — Shared Session Notes Utility

| Subtask | Status | Notes |
|---------|--------|-------|
| 1.1 Create `server/app/utils/__init__.py` | NOT_STARTED | |
| 1.2 Create `server/app/utils/session_notes.py` | NOT_STARTED | All 4 new adaptive fields included |
| 1.3 Refactor `session.py` — replace local helpers with imports | NOT_STARTED | |
| 1.4 Refactor `patient.py` — replace local helpers with imports | NOT_STARTED | |

---

## Phase 2 — Schema + Plan Generator Changes

| Subtask | Status | Notes |
|---------|--------|-------|
| 2.1 Add `initial_level_name` to `PlanTaskAssignment` model | NOT_STARTED | |
| 2.2 Apply schema change to DB (reset_db --seed OR ALTER TABLE) | NOT_STARTED | Document which path used |
| 2.3 Update `plan_generator.py` to populate `initial_level_name` | NOT_STARTED | |

---

## Phase 3 — Analysis Task Adaptive Engine

| Subtask | Status | Notes |
|---------|--------|-------|
| 3.1 Import session_notes utility in `analysis.py` | NOT_STARTED | |
| 3.2 Add `_read_session_notes(cur, session_id)` helper | NOT_STARTED | |
| 3.3 Add `_write_session_notes(cur, session_id, notes)` helper | NOT_STARTED | |
| 3.4 Add `_get_task_name(cur, task_id)` helper | NOT_STARTED | |
| 3.5 Track `attempted_prompt_ids` on every scored attempt | NOT_STARTED | Pass + fail both update the list |
| 3.6 Insert adaptive intervention block (post `_mark_prompt_terminal`) | NOT_STARTED | All 5 branches: escalated guard, force-escalate, beginner rotate, drop, increment |
| 3.7 Wire escalation notifications (`task_attempt_failed`, `task_escalated`) | NOT_STARTED | |
| 3.8 Dispatch `regenerate_plan_after_escalation.delay()` on escalation | NOT_STARTED | Requires Phase 4 to exist |

---

## Phase 4 — Plan Regeneration Celery Task

| Subtask | Status | Notes |
|---------|--------|-------|
| 4.1 Create `server/app/tasks/plan_regeneration.py` | NOT_STARTED | |
| 4.2 Implement level degradation logic (adv→int, int→beg, beg→beg) | NOT_STARTED | |
| 4.3 Archive current approved plan | NOT_STARTED | Idempotent — safe if no approved plan |
| 4.4 Generate new draft plan via psycopg2 | NOT_STARTED | Sets `initial_level_name` on all new assignments |
| 4.5 Insert `plan_revision_history` row | NOT_STARTED | action = 'auto_regenerated_after_escalation' |
| 4.6 Create `plan_regenerated_pending_approval` notification | NOT_STARTED | |
| 4.7 Publish Redis event to therapist WS channel | NOT_STARTED | |

---

## Phase 5 — Patient Router Updates

| Subtask | Status | Notes |
|---------|--------|-------|
| 5.1 Add `TodayTasksResponse` schema to `schemas/patient.py` | NOT_STARTED | `{ assignments, any_escalated }` |
| 5.2 Add `escalated` + `escalation_message` to `TaskExerciseStateOut` schema | NOT_STARTED | Both optional |
| 5.3 Update `_resolve_task_level_name` — add `initial_level_name` param | NOT_STARTED | |
| 5.4 Implement week-over-week logic in `_resolve_task_level_name` | NOT_STARTED | ISO week check, terminal outcome avg, floor clamp |
| 5.5 Update `_build_task_state` — escalation gate return | NOT_STARTED | Returns early with escalated=True if notes["escalated"] |
| 5.6 Update `_build_task_state` — pass `assignment.initial_level_name` to resolver | NOT_STARTED | |
| 5.7 Update `GET /patient/tasks` to return `TodayTasksResponse` envelope | NOT_STARTED | Compute `any_escalated` from active session notes |

---

## Phase 6 — Session Router Hard-Stop Guards

| Subtask | Status | Notes |
|---------|--------|-------|
| 6.1 Import `parse_session_notes` from utils in `session.py` | NOT_STARTED | Remove local `_parse_session_notes` usage |
| 6.2 Add escalation 403 guard to `POST /session/start` | NOT_STARTED | Check all today's therapy sessions for escalated=true |
| 6.3 Add escalation 403 guard to `POST /session/{session_id}/attempt` | NOT_STARTED | Parse session_notes after session load |

---

## Phase 7 — Client Updates

| Subtask | Status | Notes |
|---------|--------|-------|
| 7.1 Add `TodayTasksResponse` type | NOT_STARTED | `{ assignments: TaskAssignmentOut[], any_escalated: boolean }` |
| 7.2 Add `escalated` + `escalation_message` to `TaskExerciseState` type | NOT_STARTED | Both optional |
| 7.3 Update `tasks/page.tsx` — use `.assignments` instead of raw array | NOT_STARTED | |
| 7.4 Update `tasks/page.tsx` — render `any_escalated` full-day locked banner | NOT_STARTED | |
| 7.5 Update `tasks/[assignmentId]/page.tsx` — handle `escalated` state | NOT_STARTED | Redirect to tasks list with toast |
| 7.6 Update `tasks/[assignmentId]/page.tsx` — handle `alternate_prompt` decision | NOT_STARTED | Show adjustment toast before advancing |
