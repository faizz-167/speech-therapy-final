# Adaptive Engine Implementation — Status Tracker

## Legend
- `NOT_STARTED` — work not yet begun
- `IN_PROGRESS` — currently being executed
- `COMPLETED` — all subtasks done and validation passed

---

## Phase Overview

| Phase | Title | Status | Notes |
|-------|-------|--------|-------|
| 1 | Shared Session Notes Utility | COMPLETED | |
| 2 | Schema + Plan Generator Changes | COMPLETED | |
| 3 | Analysis Task — Adaptive Engine | COMPLETED | Depends on Phase 1 + Phase 2 |
| 4 | Plan Regeneration Celery Task | COMPLETED | Depends on Phase 2 |
| 5 | Patient Router Updates | COMPLETED | Depends on Phase 1 + Phase 2 |
| 6 | Session Router Hard-Stop Guards | COMPLETED | Depends on Phase 1 |
| 7 | Client Updates | COMPLETED | Depends on Phase 3 + Phase 5 |

---

## Phase 1 — Shared Session Notes Utility

| Subtask | Status | Notes |
|---------|--------|-------|
| 1.1 Create `server/app/utils/__init__.py` | COMPLETED | |
| 1.2 Create `server/app/utils/session_notes.py` | COMPLETED | All 4 new adaptive fields included |
| 1.3 Refactor `session.py` — replace local helpers with imports | COMPLETED | |
| 1.4 Refactor `patient.py` — replace local helpers with imports | COMPLETED | |

---

## Phase 2 — Schema + Plan Generator Changes

| Subtask | Status | Notes |
|---------|--------|-------|
| 2.1 Add `initial_level_name` to `PlanTaskAssignment` model | COMPLETED | |
| 2.2 Apply schema change to DB (reset_db --seed OR ALTER TABLE) | COMPLETED | |
| 2.3 Update `plan_generator.py` to populate `initial_level_name` | COMPLETED | |

---

## Phase 3 — Analysis Task Adaptive Engine

| Subtask | Status | Notes |
|---------|--------|-------|
| 3.1 Import session_notes utility in `analysis.py` | COMPLETED | |
| 3.2 Add `_read_session_notes(cur, session_id)` helper | COMPLETED | |
| 3.3 Add `_write_session_notes(cur, session_id, notes)` helper | COMPLETED | |
| 3.4 Add `_get_task_name(cur, task_id)` helper | COMPLETED | |
| 3.5 Track `attempted_prompt_ids` on every scored attempt | COMPLETED | Pass + fail both update the list (no-speech and normal paths) |
| 3.6 Insert adaptive intervention block (post `_mark_prompt_terminal`) | COMPLETED | All 5 branches: escalated guard, force-escalate, beginner rotate, drop, increment |
| 3.7 Wire escalation notifications (`task_attempt_failed`, `task_escalated`) | COMPLETED | |
| 3.8 Dispatch `regenerate_plan_after_escalation.delay()` on escalation | COMPLETED | Wired in analysis.py both escalation branches |

---

## Phase 4 — Plan Regeneration Celery Task

| Subtask | Status | Notes |
|---------|--------|-------|
| 4.1 Create `server/app/tasks/plan_regeneration.py` | COMPLETED | |
| 4.2 Implement level degradation logic (adv→int, int→beg, beg→beg) | COMPLETED | |
| 4.3 Archive current approved plan | COMPLETED | Idempotent — safe if no approved plan |
| 4.4 Generate new draft plan via psycopg2 | COMPLETED | Sets `initial_level_name` on all new assignments |
| 4.5 Insert `plan_revision_history` row | COMPLETED | action = 'auto_regenerated_after_escalation' |
| 4.6 Create `plan_regenerated_pending_approval` notification | COMPLETED | |
| 4.7 Publish Redis event to therapist WS channel | COMPLETED | |

---

## Phase 5 — Patient Router Updates

| Subtask | Status | Notes |
|---------|--------|-------|
| 5.1 Add `TodayTasksResponse` schema to `schemas/patient.py` | COMPLETED | `{ assignments, any_escalated }` |
| 5.2 Add `escalated` + `escalation_message` to `TaskExerciseStateOut` schema | COMPLETED | Both optional |
| 5.3 Update `_resolve_task_level_name` — add `initial_level_name` param | COMPLETED | |
| 5.4 Implement week-over-week logic in `_resolve_task_level_name` | COMPLETED | ISO week check, terminal outcome avg, floor clamp |
| 5.5 Update `_build_task_state` — escalation gate return | COMPLETED | Returns early with escalated=True if notes["escalated"] |
| 5.6 Update `_build_task_state` — pass `assignment.initial_level_name` to resolver | COMPLETED | |
| 5.7 Update `GET /patient/tasks` to return `TodayTasksResponse` envelope | COMPLETED | Compute `any_escalated` from active session notes |

---

## Phase 6 — Session Router Hard-Stop Guards

| Subtask | Status | Notes |
|---------|--------|-------|
| 6.1 Import `parse_session_notes` from utils in `session.py` | COMPLETED | Already done by Phase 1 |
| 6.2 Add escalation 403 guard to `POST /session/start` | COMPLETED | Part A (loop) + Part B (full-day pause) |
| 6.3 Add escalation 403 guard to `POST /session/{session_id}/attempt` | COMPLETED | After session ownership check |

---

## Phase 7 — Client Updates

| Subtask | Status | Notes |
|---------|--------|-------|
| 7.1 Add `TodayTasksResponse` type | COMPLETED | Added to `client/types/plans.ts` |
| 7.2 Add `escalated` + `escalation_message` to `TaskExerciseState` type | COMPLETED | Added to `client/types/session.ts` |
| 7.3 Update `tasks/page.tsx` — use `.assignments` instead of raw array | COMPLETED | |
| 7.4 Update `tasks/page.tsx` — render `any_escalated` full-day locked banner | COMPLETED | |
| 7.5 Update `tasks/[assignmentId]/page.tsx` — handle `escalated` state | COMPLETED | Redirect on state load + WS/poll result |
| 7.6 Update `tasks/[assignmentId]/page.tsx` — handle `alternate_prompt` decision | COMPLETED | Toast + finishOrAdvance on WS/poll result |
