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
