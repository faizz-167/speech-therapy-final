# Phase 1 — Shared Session Notes Utility

## Objective
Create a single source of truth for all `session_notes` JSON logic. Currently, `_default_session_notes`, `_parse_session_notes`, and `_serialize_session_notes` are duplicated across `patient.py` and `session.py` (and will be needed in `analysis.py` and `plan_regeneration.py`). This phase consolidates them before any adaptive state is added, so new fields are defined exactly once.

## Dependencies
None — this phase has no upstream code dependencies and should be executed first.

## Subtasks

### 1.1 — Create `server/app/utils/__init__.py`
- Create an empty `__init__.py` to make `utils` a proper Python package.
- File: `server/app/utils/__init__.py`
- Content: empty (or `# utils package`)

### 1.2 — Create `server/app/utils/session_notes.py`
Create the following three functions. Include **all four new adaptive fields** in the defaults.

```python
import json

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

def parse_session_notes(raw: str | None, assignment_id=None, task_id=None) -> dict:
    """
    Safe JSON parse. Merges parsed dict on top of defaults so all keys
    are guaranteed present. Normalizes list fields to lists.
    """
    defaults = default_session_notes(assignment_id=assignment_id, task_id=task_id)
    if not raw:
        return defaults
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return defaults
    if not isinstance(parsed, dict):
        return defaults
    merged = {**defaults, **parsed}
    # normalize list fields in case stored value is None
    for key in ("completed_prompt_ids", "passed_prompt_ids", "attempted_prompt_ids"):
        if not isinstance(merged.get(key), list):
            merged[key] = []
    return merged

def serialize_session_notes(notes: dict) -> str:
    """JSON dump with normalized list fields."""
    for key in ("completed_prompt_ids", "passed_prompt_ids", "attempted_prompt_ids"):
        if not isinstance(notes.get(key), list):
            notes[key] = []
    return json.dumps(notes)
```

### 1.3 — Refactor `server/app/routers/session.py`
- Remove the local `_default_session_notes` function (lines 24-32).
- Remove the local `_parse_session_notes` function (lines 35-50).
- Add import at top: `from app.utils.session_notes import default_session_notes, parse_session_notes`
- Replace all usages:
  - `_default_session_notes(...)` → `default_session_notes(...)`
  - `_parse_session_notes(...)` → `parse_session_notes(...)`
  - `json.dumps(_default_session_notes(...))` → `serialize_session_notes(default_session_notes(...))`
    - Also add `serialize_session_notes` to the import line.

**Locations to update in `session.py`:**
- Line 87: `notes = _parse_session_notes(existing_session.session_notes)` → `parse_session_notes(...)`
- Line 106-110: `session_notes=json.dumps(_default_session_notes(...))` → `session_notes=serialize_session_notes(default_session_notes(...))`

### 1.4 — Refactor `server/app/routers/patient.py`
- Locate and remove local `_default_session_notes`, `_parse_session_notes`, `_serialize_session_notes` definitions.
- Add import: `from app.utils.session_notes import default_session_notes, parse_session_notes, serialize_session_notes`
- Replace every call site with the imported function names (drop the leading underscore).
- Do NOT change any other logic in `patient.py` — that happens in Phase 5.

## Execution Plan

1. Create `server/app/utils/__init__.py` (empty file).
2. Create `server/app/utils/session_notes.py` with the three functions above.
3. Open `server/app/routers/session.py`:
   - Add import.
   - Delete local helper functions.
   - Update all call sites.
4. Open `server/app/routers/patient.py`:
   - Add import.
   - Delete local helper functions.
   - Update all call sites.
5. Update `status.md`: mark subtasks 1.1–1.4 as COMPLETED, mark Phase 1 as COMPLETED.

## Validation Criteria
- [ ] `server/app/utils/session_notes.py` exists with all three functions.
- [ ] All four adaptive fields (`adaptive_interventions`, `attempted_prompt_ids`, `escalated`, `escalation_level`) present in `default_session_notes` return value.
- [ ] No remaining definition of `_default_session_notes` anywhere in `session.py` or `patient.py`.
- [ ] No remaining definition of `_parse_session_notes` anywhere in `session.py` or `patient.py`.
- [ ] No remaining definition of `_serialize_session_notes` anywhere in `patient.py`.
- [ ] `python -c "from app.utils.session_notes import default_session_notes, parse_session_notes, serialize_session_notes; print('OK')"` succeeds from the `server/` directory.
