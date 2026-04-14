import uuid
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import String, cast, select

from app.models.content import Task, TaskDefectMapping, TaskLevel
from app.models.plan import TherapyPlan, PlanTaskAssignment, PlanRevisionHistory
from app.models.users import Patient, Therapist


def _normalize_task_level_name(level: str | None) -> str:
    normalized = (level or "").strip().lower()
    return {
        "easy": "beginner",
        "medium": "intermediate",
        "advanced": "advanced",
        "beginner": "beginner",
        "elementary": "elementary",
        "intermediate": "intermediate",
        "expert": "expert",
    }.get(normalized, "beginner")


async def generate_weekly_plan(
    patient: Patient,
    therapist: Therapist,
    baseline_level: str,
    db: AsyncSession,
) -> TherapyPlan:
    baseline_level = _normalize_task_level_name(baseline_level)
    defect_ids = (patient.pre_assigned_defect_ids or {}).get("defect_ids", [])
    if not defect_ids:
        raise ValueError("Patient has no assigned defects")

    mapping_result = await db.execute(
        select(TaskDefectMapping.task_id)
        .where(TaskDefectMapping.defect_id.in_(defect_ids))
        .distinct()
    )
    task_ids = [row[0] for row in mapping_result.fetchall()]

    level_result = await db.execute(
        select(TaskLevel.task_id).where(
            TaskLevel.task_id.in_(task_ids),
            cast(TaskLevel.level_name, String) == baseline_level,
        )
    )
    eligible_task_ids = [row[0] for row in level_result.fetchall()]

    tasks_result = await db.execute(select(Task).where(Task.task_id.in_(eligible_task_ids)))
    tasks = tasks_result.scalars().all()

    if not tasks:
        level_result = await db.execute(
            select(TaskLevel.task_id).where(
                TaskLevel.task_id.in_(task_ids),
                cast(TaskLevel.level_name, String) == "beginner",
            )
        )
        eligible_task_ids = [row[0] for row in level_result.fetchall()]
        tasks_result = await db.execute(select(Task).where(Task.task_id.in_(eligible_task_ids)))
        tasks = tasks_result.scalars().all()
        baseline_level = "beginner"

    today = date.today()
    end_date = today + timedelta(days=6)
    plan = TherapyPlan(
        plan_id=uuid.uuid4(),
        patient_id=patient.patient_id,
        therapist_id=therapist.therapist_id,
        plan_name=f"Week of {today.strftime('%b %d, %Y')} — {baseline_level.capitalize()} Level",
        start_date=today,
        end_date=end_date,
        status="draft",
        goals=f"Improve speech clarity at {baseline_level} level targeting assigned defects.",
    )
    db.add(plan)
    await db.flush()

    start_day_index = today.weekday()
    slots = [
        ((start_day_index + day_offset) % 7, slot)
        for day_offset in range(7)
        for slot in range(2)
    ]
    for i, task in enumerate(tasks[:14]):
        day_index, priority = slots[i] if i < len(slots) else (i % 7, i // 7)
        assignment = PlanTaskAssignment(
            assignment_id=uuid.uuid4(),
            plan_id=plan.plan_id,
            task_id=task.task_id,
            therapist_id=therapist.therapist_id,
            day_index=day_index,
            priority_order=priority,
            status="pending",
            initial_level_name=baseline_level,
        )
        db.add(assignment)

    revision = PlanRevisionHistory(
        plan_id=plan.plan_id,
        therapist_id=therapist.therapist_id,
        action="generate",
        new_value={"task_count": len(tasks[:14]), "baseline_level": baseline_level},
        note=f"Plan auto-generated at {baseline_level} level for {len(defect_ids)} defect(s).",
    )
    db.add(revision)
    await db.commit()
    await db.refresh(plan)
    return plan
