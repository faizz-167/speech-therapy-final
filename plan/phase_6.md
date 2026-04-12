# Phase 6 — Session Router Hard-Stop Guards

## Objective
Enforce the escalation lock at the API layer in `server/app/routers/session.py`. The client-side `any_escalated` flag (Phase 5) can be bypassed by direct API calls. These 403 guards ensure no new session can be started and no attempt can be submitted when any of today's tasks is escalated — regardless of what the client sends.

## Dependencies
- Phase 1 COMPLETED (`parse_session_notes` from the shared utility must be available).

## Subtasks

### 6.1 — Import `parse_session_notes` from utils in `session.py`
At the top of `server/app/routers/session.py`, replace the local `_parse_session_notes` import block.

After Phase 1 refactors `session.py`, the local `_parse_session_notes` will already be removed and replaced with the import. **Verify this is already done** before proceeding. If Phase 1 is COMPLETED, this subtask is effectively already done — just confirm the import line exists:
```python
from app.utils.session_notes import default_session_notes, parse_session_notes, serialize_session_notes
```

### 6.2 — Add escalation 403 guard to `POST /session/start`
**Critical placement detail:** The existing handler (lines 86–89) iterates sessions and **returns early** when it finds a matching non-completed session for the same `assignment_id`. An escalated session is not completed, so it matches and the early return fires before any guard placed after the loop. The guard must be inserted **inside the loop**, before the early return, not after it.

**Two-part change:**

**Part A — Inside the existing-session loop** (replace lines ~86-89):
```python
for existing_session in existing_result.scalars().all():
    notes = parse_session_notes(existing_session.session_notes)
    if notes.get("assignment_id") == body.assignment_id and not notes.get("completed"):
        # Hard stop: escalated sessions cannot be resumed
        if notes.get("escalated"):
            raise HTTPException(
                status_code=403,
                detail="Session locked — this task requires therapist review before you can continue."
            )
        return {"session_id": str(existing_session.session_id)}
```

**Part B — Before new session creation** (insert before `session = Session(...)`):
```python
# Full-day pause: if any of today's therapy sessions is escalated, block new session creation
from datetime import date
today = date.today()
today_sessions_result = await db.execute(
    select(Session).where(
        Session.patient_id == patient.patient_id,
        Session.session_type == "therapy",
        func.date(Session.session_date) == today,
    )
)
for sess in today_sessions_result.scalars().all():
    notes = parse_session_notes(sess.session_notes)
    if notes.get("escalated"):
        raise HTTPException(
            status_code=403,
            detail="Session locked — one of today's tasks requires therapist review before you can continue."
        )
```

**Note:** `func` is already imported from `sqlalchemy`. `date` should be imported at the top (`from datetime import date`). Verify both are present. Part B is the broader full-day pause; Part A is the narrower resume-path block — both are required.

### 6.3 — Add escalation 403 guard to `POST /session/{session_id}/attempt`
**Location:** `submit_attempt` handler, after `session = await db.get(Session, session_id)` and the ownership check.

```python
notes = parse_session_notes(session.session_notes)
if notes.get("escalated"):
    raise HTTPException(
        status_code=403,
        detail="This session is locked pending therapist review."
    )
```

**Insert point:** Immediately after line 132 (`if not session or session.patient_id != patient.patient_id: raise HTTPException(404, ...)`), before the prompt lookup.

## Execution Plan

1. Confirm Phase 1 is COMPLETED (import exists in `session.py`).
2. Open `server/app/routers/session.py`.
3. Add today's-session escalation check in `start_session` (subtask 6.2).
4. Add per-session escalation check in `submit_attempt` (subtask 6.3).
5. Update `status.md`.

## Validation Criteria
- [ ] `parse_session_notes` imported from `app.utils.session_notes` in `session.py` (no local copy).
- [ ] `POST /session/start` raises 403 when the matched existing session has `escalated=True` (inside the loop, before early return).
- [ ] `POST /session/start` also raises 403 for new session creation when any of today's sessions has `escalated=True` (full-day pause).
- [ ] `POST /session/{session_id}/attempt` raises 403 immediately after session load if `session.session_notes` has `escalated=True`.
- [ ] Non-escalated sessions are unaffected — no behavioral change for normal flow.
- [ ] The 403 message is human-readable (used by the client to show an error state).
