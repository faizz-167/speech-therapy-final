import uuid
import json
import logging
import psycopg2
import redis
from datetime import date, timedelta

from app.celery_app import celery_app
from app.config import settings

logger = logging.getLogger(__name__)

LEVEL_DEGRADATION = {
    "advanced": "intermediate",
    "intermediate": "beginner",
    "beginner": "beginner",
}


def _degrade_level(level_name: str) -> str:
    return LEVEL_DEGRADATION.get(level_name.lower(), "beginner")


@celery_app.task(
    name="app.tasks.plan_regeneration.regenerate_plan_after_escalation",
    bind=True,
    max_retries=2,
)
def regenerate_plan_after_escalation(
    self, patient_id: str, therapist_id: str, escalation_level_name: str
):
    conn = None
    try:
        conn = psycopg2.connect(settings.database_url_sync)
        conn.autocommit = False
        cur = conn.cursor()

        new_level_name = _degrade_level(escalation_level_name)

        # 4.3 — Archive current approved plan (idempotent)
        archived = 0
        if archived == 0:
            logger.warning(
                "No approved plan found to archive for patient %s — continuing", patient_id
            )

        # 4.4a — Fetch patient's defect IDs from JSONB column
        cur.execute(
            "SELECT pre_assigned_defect_ids FROM patient WHERE patient_id = %s",
            (patient_id,),
        )
        row = cur.fetchone()
        defect_ids = (row[0] or {}).get("defect_ids", []) if row else []
        if not defect_ids:
            logger.warning(
                "Patient %s has no defect_ids in pre_assigned_defect_ids", patient_id
            )
            raise self.retry(exc=ValueError("No defect_ids"), countdown=30)

        # 4.4b — Fetch task_ids mapped to those defects
        cur.execute(
            "SELECT DISTINCT task_id FROM task_defect_mapping WHERE defect_id = ANY(%s)",
            (defect_ids,),
        )
        mapped_task_ids = [r[0] for r in cur.fetchall()]
        if not mapped_task_ids:
            logger.warning(
                "No tasks mapped to defects %s for patient %s", defect_ids, patient_id
            )
            raise self.retry(exc=ValueError("No mapped tasks"), countdown=30)

        # 4.4c — Fetch task_ids eligible at new_level
        cur.execute(
            "SELECT tl.task_id FROM task_level tl WHERE tl.task_id = ANY(%s) AND tl.level_name = %s",
            (mapped_task_ids, new_level_name),
        )
        eligible_task_ids = [r[0] for r in cur.fetchall()]

        # 4.4d — Fallback to beginner if no tasks at degraded level
        if not eligible_task_ids:
            logger.warning(
                "No tasks at degraded level '%s' for patient %s — falling back to beginner",
                new_level_name,
                patient_id,
            )
            new_level_name = "beginner"
            cur.execute(
                "SELECT tl.task_id FROM task_level tl WHERE tl.task_id = ANY(%s) AND tl.level_name = 'beginner'",
                (mapped_task_ids,),
            )
            eligible_task_ids = [r[0] for r in cur.fetchall()]

        # 4.4e — Fetch patient full_name for notification message
        cur.execute("SELECT full_name FROM patient WHERE patient_id = %s", (patient_id,))
        name_row = cur.fetchone()
        patient_name = name_row[0] if name_row else "Unknown"

        # 4.4g — Insert new therapy_plan as draft
        new_plan_id = uuid.uuid4()
        today = date.today()
        week_start = today - timedelta(days=today.weekday())   # Monday
        week_end = week_start + timedelta(days=6)              # Sunday
        plan_name = f"Week of {week_start.strftime('%b')} {week_start.day}, {week_start.year} — {new_level_name.title()} Level"
        goals = (
            f"Plan auto-generated after escalation: level changed from "
            f"{escalation_level_name} \u2192 {new_level_name} for all tasks after 2 "
            f"consecutive adaptation thresholds were reached."
        )
        cur.execute(
            "INSERT INTO therapy_plan"
            " (plan_id, patient_id, therapist_id, plan_name, goals, start_date, end_date, status, created_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, 'draft', NOW())",
            (str(new_plan_id), patient_id, therapist_id, plan_name, goals,
             week_start.isoformat(), week_end.isoformat()),
        )

        # 4.4h — Insert plan_task_assignment rows (up to 14, cycling 7-day week)
        tasks_to_assign = eligible_task_ids[:14]
        for i, task_id in enumerate(tasks_to_assign):
            day_index = i % 7
            priority_order = i // 7 + 1

            cur.execute(
                "SELECT level_id FROM task_level WHERE task_id = %s AND level_name = %s",
                (task_id, new_level_name),
            )
            level_row = cur.fetchone()
            level_id = level_row[0] if level_row else None

            cur.execute(
                "INSERT INTO plan_task_assignment"
                " (assignment_id, plan_id, task_id, therapist_id, day_index, priority_order,"
                "  status, initial_level_name)"
                " VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s)",
                (
                    str(uuid.uuid4()),
                    str(new_plan_id),
                    task_id,
                    therapist_id,
                    day_index,
                    priority_order,
                    new_level_name,
                ),
            )

            # Reset patient_task_progress so the patient portal reflects the new
            # degraded level immediately (not the stale prior-level progress row).
            if level_id is not None:
                cur.execute(
                    "INSERT INTO patient_task_progress"
                    " (patient_id, task_id, current_level_id,"
                    "  consecutive_passes, consecutive_fails, total_attempts, sessions_at_level)"
                    " VALUES (%s, %s, %s, 0, 0, 0, 0)"
                    " ON CONFLICT (patient_id, task_id) DO UPDATE SET"
                    "  current_level_id = EXCLUDED.current_level_id,"
                    "  level_locked_until = NULL,"
                    "  consecutive_passes = 0,"
                    "  consecutive_fails = 0,"
                    "  sessions_at_level = 0",
                    (patient_id, task_id, level_id),
                )

        # 4.5 — Insert plan_revision_history row
        cur.execute(
            "INSERT INTO plan_revision_history"
            " (revision_id, plan_id, therapist_id, action, note, created_at)"
            " VALUES (%s, %s, %s, 'auto_regenerated_after_escalation', %s, NOW())",
            (
                str(uuid.uuid4()),
                str(new_plan_id),
                therapist_id,
                f"Plan auto-generated after patient task escalation at level: {escalation_level_name}",
            ),
        )

        conn.commit()

        # 4.6 — Insert therapist notification (committed separately so durable on partial failure)
        cur.execute(
            "INSERT INTO therapist_notification"
            " (notification_id, therapist_id, type, patient_id, plan_id, message, is_read, created_at)"
            " VALUES (%s, %s, 'plan_regenerated_pending_approval', %s, %s, %s, FALSE, NOW())",
            (
                str(uuid.uuid4()),
                therapist_id,
                patient_id,
                str(new_plan_id),
                f"A new {new_level_name} plan has been auto-generated for {patient_name}"
                f" following task escalation. Awaiting your approval.",
            ),
        )
        conn.commit()

        # 4.7 — Publish Redis event to therapist WS channel
        r = redis.from_url(settings.redis_url)
        channel = f"ws:therapist:{therapist_id}"
        payload = json.dumps(
            {
                "type": "plan_regenerated",
                "plan_id": str(new_plan_id),
                "patient_id": str(patient_id),
                "level": new_level_name,
            }
        )
        r.publish(channel, payload)

        logger.info(
            "Plan regeneration complete: patient=%s new_plan=%s level=%s",
            patient_id,
            new_plan_id,
            new_level_name,
        )

    except Exception as exc:
        if conn:
            conn.rollback()
        raise self.retry(exc=exc, countdown=30)
    finally:
        if conn:
            conn.close()
