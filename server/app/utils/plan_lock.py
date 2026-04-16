import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.plan import PlanRevisionHistory, TherapyPlan
from app.models.scoring import Session
from app.utils.session_notes import parse_session_notes, serialize_session_notes


async def patient_has_pending_plan_review(
    patient_id: uuid.UUID,
    db: AsyncSession,
) -> bool:
    result = await db.execute(
        select(Session)
        .where(
            Session.patient_id == patient_id,
            Session.session_type == "therapy",
        )
        .order_by(Session.session_date.desc())
    )
    for session in result.scalars().all():
        notes = parse_session_notes(session.session_notes)
        if notes.get("escalated") or notes.get("locked_for_review"):
            return True
    return False


async def clear_patient_plan_review_lock(
    patient_id: uuid.UUID,
    db: AsyncSession,
) -> None:
    result = await db.execute(
        select(Session).where(
            Session.patient_id == patient_id,
            Session.session_type == "therapy",
        )
    )
    for session in result.scalars().all():
        notes = parse_session_notes(session.session_notes)
        if not (notes.get("escalated") or notes.get("locked_for_review")):
            continue
        notes["escalated"] = False
        notes["locked_for_review"] = False
        notes["escalation_level"] = None
        session.session_notes = serialize_session_notes(notes)


async def has_pending_regenerated_draft(
    patient_id: uuid.UUID,
    db: AsyncSession,
) -> bool:
    result = await db.execute(
        select(TherapyPlan.plan_id)
        .join(PlanRevisionHistory, TherapyPlan.plan_id == PlanRevisionHistory.plan_id)
        .where(
            TherapyPlan.patient_id == patient_id,
            TherapyPlan.status == "draft",
            PlanRevisionHistory.action == "auto_regenerated_after_escalation",
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None

