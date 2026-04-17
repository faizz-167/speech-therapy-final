"""Session queue and adaptive difficulty management.

Handles the in-session prompt queue: tracking pending/completed items,
level downgrades, remedial item injection, and escalation to therapist review.
"""

import json
import uuid

from app.constants import ESCALATION_INTERVENTION_LIMIT, MAX_ATTEMPTS_PER_PROMPT
from app.utils.session_notes import parse_session_notes, serialize_session_notes


LEVEL_DROP_MAP = {
    "advanced": "intermediate",
    "intermediate": "beginner",
    "beginner": "beginner",
}


# ---------------------------------------------------------------------------
# DB read helpers (cursor-based, sync)
# ---------------------------------------------------------------------------

def read_session_notes(cur, session_id: str) -> dict:
    cur.execute(
        "SELECT session_notes FROM session WHERE session_id = %s",
        (session_id,),
    )
    row = cur.fetchone()
    raw = row[0] if row else None
    return parse_session_notes(raw)


def write_session_notes(cur, session_id: str, notes: dict) -> None:
    cur.execute(
        "UPDATE session SET session_notes = %s WHERE session_id = %s",
        (serialize_session_notes(notes), session_id),
    )


def get_task_name(cur, task_id: str) -> str:
    cur.execute("SELECT name FROM task WHERE task_id = %s", (task_id,))
    row = cur.fetchone()
    return row[0] if row else "Unknown Task"


def get_level_name_from_level_id(cur, level_id: str | None) -> str | None:
    if not level_id:
        return None
    cur.execute("SELECT level_name FROM task_level WHERE level_id = %s", (level_id,))
    row = cur.fetchone()
    return str(row[0]).lower() if row and row[0] else None


def get_prompt_ids_for_level(cur, task_id: str, level_name: str) -> list[str]:
    cur.execute(
        "SELECT p.prompt_id"
        " FROM prompt p"
        " JOIN task_level tl ON tl.level_id = p.level_id"
        " WHERE tl.task_id = %s AND tl.level_name = %s"
        " ORDER BY p.prompt_id ASC",
        (task_id, level_name),
    )
    return [str(row[0]) for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Queue item operations
# ---------------------------------------------------------------------------

def find_pending_queue_item(notes: dict, prompt_id: str) -> tuple[int | None, dict | None]:
    queue_items = notes.get("queue_items") or []
    for idx, item in enumerate(queue_items):
        if item.get("status") == "pending" and str(item.get("prompt_id")) == str(prompt_id):
            return idx, item
    for idx, item in enumerate(queue_items):
        if item.get("status") == "pending":
            return idx, item
    return None, None


def reassign_pending_queue_items(cur, task_id: str, notes: dict, new_level_name: str) -> None:
    queue_items = notes.get("queue_items") or []
    pending_indices = [idx for idx, item in enumerate(queue_items) if item.get("status") == "pending"]
    prompt_ids = get_prompt_ids_for_level(cur, task_id, new_level_name)
    if not prompt_ids:
        return
    for offset, idx in enumerate(pending_indices):
        previous_level_name = queue_items[idx].get("level_name")
        queue_items[idx]["level_name"] = new_level_name
        queue_items[idx]["prompt_id"] = prompt_ids[offset % len(prompt_ids)]
        queue_items[idx]["adapted_from_level"] = queue_items[idx].get("adapted_from_level") or previous_level_name
    notes["queue_items"] = queue_items


def append_remedial_queue_item(cur, task_id: str, notes: dict, new_level_name: str, reason_code: str) -> None:
    prompt_ids = get_prompt_ids_for_level(cur, task_id, new_level_name)
    if not prompt_ids:
        return
    queue_items = notes.get("queue_items") or []
    used_prompt_ids = {str(item.get("prompt_id")) for item in queue_items}
    chosen_prompt_id = next((pid for pid in prompt_ids if pid not in used_prompt_ids), prompt_ids[0])
    queue_items.append({
        "queue_item_id": str(uuid.uuid4()),
        "prompt_id": chosen_prompt_id,
        "level_name": new_level_name,
        "source_type": "remedial",
        "status": "pending",
        "attempts_used": 0,
        "adapted_from_level": None,
        "reason_code": reason_code,
    })
    notes["queue_items"] = queue_items


# ---------------------------------------------------------------------------
# Adaptation report
# ---------------------------------------------------------------------------

def build_adaptation_report(cur, session_id: str, task_id: str, task_name: str, notes: dict) -> dict:
    cur.execute(
        "SELECT spa.prompt_id, spa.attempt_number, spa.result,"
        " asd.word_accuracy, asd.fluency_score, asd.speech_rate_score,"
        " asd.confidence_score, asd.dominant_emotion, asd.fail_reason"
        " FROM session_prompt_attempt spa"
        " LEFT JOIN attempt_score_detail asd ON asd.attempt_id = spa.attempt_id"
        " WHERE spa.session_id = %s"
        " ORDER BY spa.created_at ASC",
        (session_id,),
    )
    attempt_rows = cur.fetchall()
    attempts = [
        {
            "prompt_id": str(row[0]),
            "attempt_number": int(row[1]) if row[1] is not None else None,
            "result": row[2],
            "word_accuracy": float(row[3]) if row[3] is not None else None,
            "fluency_score": float(row[4]) if row[4] is not None else None,
            "speech_rate_score": float(row[5]) if row[5] is not None else None,
            "confidence_score": float(row[6]) if row[6] is not None else None,
            "dominant_emotion": row[7],
            "fail_reason": row[8],
        }
        for row in attempt_rows
    ]
    return {
        "task_id": task_id,
        "task_name": task_name,
        "adaptation_count": int(notes.get("adaptive_interventions") or 0),
        "current_level": notes.get("current_queue_level"),
        "adaptation_history": notes.get("adaptation_history") or [],
        "queue_items": notes.get("queue_items") or [],
        "attempts": attempts,
    }


# ---------------------------------------------------------------------------
# Mark prompt as terminally completed
# ---------------------------------------------------------------------------

def mark_prompt_terminal(cur, session_id: str, prompt_id: str, pass_fail: str, attempt_number: int) -> None:
    if pass_fail != "pass" and attempt_number < MAX_ATTEMPTS_PER_PROMPT:
        return

    cur.execute("SELECT session_notes FROM session WHERE session_id = %s", (session_id,))
    row = cur.fetchone()
    session_notes = {}
    if row and row[0]:
        try:
            session_notes = json.loads(row[0])
        except (TypeError, ValueError):
            session_notes = {}

    completed_prompt_ids = list(session_notes.get("completed_prompt_ids") or [])
    passed_prompt_ids = list(session_notes.get("passed_prompt_ids") or [])

    if prompt_id not in completed_prompt_ids:
        completed_prompt_ids.append(prompt_id)
    if pass_fail == "pass" and prompt_id not in passed_prompt_ids:
        passed_prompt_ids.append(prompt_id)

    session_notes["completed_prompt_ids"] = completed_prompt_ids
    session_notes["passed_prompt_ids"] = passed_prompt_ids
    cur.execute(
        "UPDATE session SET session_notes = %s WHERE session_id = %s",
        (json.dumps(session_notes), session_id),
    )


# ---------------------------------------------------------------------------
# Core queue result handler
# ---------------------------------------------------------------------------

def apply_session_queue_result(
    cur,
    session_id: str,
    task_id: str,
    prompt_id: str,
    pass_fail: str,
    attempt_number: int,
    level_id: str | None,
    fail_reason: str | None,
    final_score: float,
    patient_id: str,
    assigned_therapist_id: str | None,
    attempt_id: str,
) -> tuple[dict, bool, dict]:
    """Process an attempt result against the session queue.

    Returns (notes, queue_active, override_dict).
    """
    notes = read_session_notes(cur, session_id)
    if str(prompt_id) not in notes["attempted_prompt_ids"]:
        notes["attempted_prompt_ids"].append(str(prompt_id))

    queue_items = notes.get("queue_items") or []
    if not notes.get("queue_initialized") or not queue_items:
        write_session_notes(cur, session_id, notes)
        return notes, False, {}

    queue_idx, queue_item = find_pending_queue_item(notes, prompt_id)
    if queue_item is None or queue_idx is None:
        write_session_notes(cur, session_id, notes)
        return notes, True, {}

    queue_item["attempts_used"] = max(int(queue_item.get("attempts_used") or 0), attempt_number)
    notes["current_queue_level"] = queue_item.get("level_name") or notes.get("current_queue_level")

    if pass_fail == "pass":
        queue_item["status"] = "passed"
        notes["queue_items"][queue_idx] = queue_item
        write_session_notes(cur, session_id, notes)
        return notes, True, {"adaptive_decision": "stay"}

    if attempt_number < MAX_ATTEMPTS_PER_PROMPT:
        notes["queue_items"][queue_idx] = queue_item
        write_session_notes(cur, session_id, notes)
        return notes, True, {}

    # Terminal failure — trigger level adaptation
    queue_item["status"] = "failed_terminal"
    queue_item["reason_code"] = fail_reason or "max_attempts_reached"
    notes["queue_items"][queue_idx] = queue_item

    current_level_name = str(
        queue_item.get("level_name")
        or get_level_name_from_level_id(cur, level_id)
        or notes.get("current_queue_level")
        or "beginner"
    ).lower()
    new_level_name = LEVEL_DROP_MAP.get(current_level_name, "beginner")

    notes["adaptive_interventions"] = int(notes.get("adaptive_interventions") or 0) + 1
    notes["current_queue_level"] = new_level_name
    notes["adaptation_history"].append({
        "queue_item_id": queue_item.get("queue_item_id"),
        "prompt_id": str(prompt_id),
        "from_level": current_level_name,
        "to_level": new_level_name,
        "attempts_used": attempt_number,
        "reason": fail_reason or "max_attempts_reached",
        "final_score": round(final_score, 2),
    })

    task_name = get_task_name(cur, str(task_id)) if task_id else "Unknown Task"

    # Escalation path: lock session when too many consecutive adaptations
    if int(notes.get("adaptive_interventions") or 0) >= ESCALATION_INTERVENTION_LIMIT:
        return _escalate_session(
            cur, notes, session_id, task_id, task_name,
            new_level_name, patient_id, assigned_therapist_id, attempt_id,
        )

    # Non-escalation: reassign pending items and add remedial
    reassign_pending_queue_items(cur, str(task_id), notes, new_level_name)
    append_remedial_queue_item(cur, str(task_id), notes, new_level_name, fail_reason or "level_downgrade")
    write_session_notes(cur, session_id, notes)

    if assigned_therapist_id:
        _create_therapist_notification(
            cur, assigned_therapist_id, "task_attempt_failed", patient_id, attempt_id,
            f"Task '{task_name}' adapted from {current_level_name} to {new_level_name} "
            f"after {attempt_number} failed attempts. A remedial exercise was appended.",
        )

    return notes, True, {"adaptive_decision": "drop", "performance_level": "needs_improvement"}


# ---------------------------------------------------------------------------
# Escalation (private)
# ---------------------------------------------------------------------------

def _escalate_session(
    cur, notes, session_id, task_id, task_name,
    new_level_name, patient_id, assigned_therapist_id, attempt_id,
) -> tuple[dict, bool, dict]:
    notes["locked_for_review"] = True
    notes["escalated"] = True
    notes["escalation_level"] = new_level_name
    for item in notes["queue_items"]:
        if item.get("status") == "pending":
            item["status"] = "skipped_due_to_lock"
    notes["adaptation_report"] = build_adaptation_report(cur, session_id, str(task_id), task_name, notes)
    write_session_notes(cur, session_id, notes)

    if assigned_therapist_id:
        _create_therapist_notification(
            cur, assigned_therapist_id, "task_escalated", patient_id, attempt_id,
            f"Task '{task_name}' is locked for therapist review after {ESCALATION_INTERVENTION_LIMIT} "
            f"level adaptations. Current level recommendation: {new_level_name}. "
            f"Review the session report before regenerating the plan.",
        )

    return notes, True, {"adaptive_decision": "escalated", "performance_level": "needs_improvement"}


# ---------------------------------------------------------------------------
# Shared notification helper (DRY — replaces 3 duplicate SQL blocks)
# ---------------------------------------------------------------------------

def _create_therapist_notification(
    cur,
    therapist_id: str,
    notification_type: str,
    patient_id: str,
    attempt_id: str,
    message: str,
) -> None:
    cur.execute(
        "INSERT INTO therapist_notification"
        " (notification_id, therapist_id, type, patient_id, attempt_id, message, is_read, created_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, false, NOW())",
        (str(uuid.uuid4()), therapist_id, notification_type, patient_id, attempt_id, message),
    )
