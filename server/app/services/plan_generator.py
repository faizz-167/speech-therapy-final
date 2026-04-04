import uuid
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.content import Task, TaskDefectMapping, TaskLevel
from app.models.plan import TherapyPlan, PlanTaskAssignment
from app.models.users import Patient, Therapist


async def generate_weekly_plan(
    patient: Patient,
    therapist: Therapist,
    baseline_level: str,
    db: AsyncSession,
) -> TherapyPlan:
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
            TaskLevel.level_name == baseline_level,
        )
    )
    eligible_task_ids = [row[0] for row in level_result.fetchall()]

    tasks_result = await db.execute(select(Task).where(Task.task_id.in_(eligible_task_ids)))
    tasks = tasks_result.scalars().all()

    if not tasks:
        level_result = await db.execute(
            select(TaskLevel.task_id).where(
                TaskLevel.task_id.in_(task_ids),
                TaskLevel.level_name == "easy",
            )
        )
        eligible_task_ids = [row[0] for row in level_result.fetchall()]
        tasks_result = await db.execute(select(Task).where(Task.task_id.in_(eligible_task_ids)))
        tasks = tasks_result.scalars().all()
        baseline_level = "easy"

    today = date.today()
    end_date = today + timedelta(days=6)
    plan = TherapyPlan(
        plan_id=uuid.uuid4(),
        patient_id=patient.patient_id,
        therapist_id=therapist.therapist_id,
        plan_name=f"Week of {today.strftime('%b %d, %Y')} — {baseline_level.capitalize()} Level",
        start_date=today.isoformat(),
        end_date=end_date.isoformat(),
        status="draft",
        goals=f"Improve speech clarity at {baseline_level} level targeting assigned defects.",
    )
    db.add(plan)
    await db.flush()

    slots = [(day, slot) for day in range(7) for slot in range(2)]
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
        )
        db.add(assignment)

    await db.commit()
    await db.refresh(plan)
    return plan
