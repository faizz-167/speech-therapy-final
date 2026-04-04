import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.auth import require_patient, require_therapist
from app.models.users import Patient, Therapist
from app.models.content import Defect
from app.models.baseline import (
    BaselineAssessment, BaselineDefectMapping, BaselineSection,
    BaselineItem, PatientBaselineResult, BaselineItemResult,
)
from app.schemas.baseline import (
    BaselineAssessmentOut, BaselineSectionOut, BaselineItemOut,
    BaselineSubmitRequest, BaselineResultOut,
)

router = APIRouter()

BASELINE_ITEM_CAP = 7


def score_to_level(score: float) -> str:
    if score >= 80:
        return "advanced"
    elif score >= 70:
        return "medium"
    return "easy"


def _allocate_items(items_by_group: dict[str, list], cap: int) -> dict[str, list]:
    """Distribute `cap` items evenly across groups. Extra items go to earlier groups."""
    n = len(items_by_group)
    if n == 0:
        return {}
    base = cap // n
    remainder = cap % n
    allocated: dict[str, list] = {}
    for idx, (key, items) in enumerate(items_by_group.items()):
        target = base + (1 if idx < remainder else 0)
        allocated[key] = items[:target]
    return allocated


@router.get("/exercises", response_model=list[BaselineAssessmentOut])
async def get_baseline_exercises(
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    if not patient.pre_assigned_defect_ids:
        raise HTTPException(400, "No defects assigned to patient")
    defect_ids = patient.pre_assigned_defect_ids.get("defect_ids", [])

    # Resolve defect categories so we can balance by category
    defect_result = await db.execute(
        select(Defect).where(Defect.defect_id.in_(defect_ids))
    )
    defects = defect_result.scalars().all()
    # Map defect_id -> category
    defect_category: dict[str, str] = {d.defect_id: d.category for d in defects}
    # Unique categories in assigned order
    seen: dict[str, int] = {}
    for did in defect_ids:
        cat = defect_category.get(did, "general")
        if cat not in seen:
            seen[cat] = len(seen)
    unique_categories = list(seen.keys())

    # Get baseline IDs mapped to each assigned defect, grouped by category
    mapping_result = await db.execute(
        select(BaselineDefectMapping)
        .where(BaselineDefectMapping.defect_id.in_(defect_ids))
    )
    mappings = mapping_result.scalars().all()
    # category -> set of baseline_ids
    category_baseline_ids: dict[str, list[str]] = {c: [] for c in unique_categories}
    seen_bids: set[str] = set()
    for m in mappings:
        cat = defect_category.get(m.defect_id, "general")
        if m.baseline_id not in seen_bids:
            category_baseline_ids.setdefault(cat, []).append(m.baseline_id)
            seen_bids.add(m.baseline_id)

    if not seen_bids:
        raise HTTPException(404, "No baseline assessments found for assigned defects")

    # Load all assessments
    all_assessments_result = await db.execute(
        select(BaselineAssessment).where(BaselineAssessment.baseline_id.in_(list(seen_bids)))
    )
    all_assessments = {a.baseline_id: a for a in all_assessments_result.scalars().all()}

    # Build category -> flat list of BaselineItemOut (in order)
    category_items: dict[str, list[BaselineItemOut]] = {c: [] for c in unique_categories}
    category_assessments: dict[str, list[BaselineAssessment]] = {c: [] for c in unique_categories}

    for cat, bids in category_baseline_ids.items():
        for bid in bids:
            a = all_assessments.get(bid)
            if not a:
                continue
            category_assessments[cat].append(a)
            sections_result = await db.execute(
                select(BaselineSection)
                .where(BaselineSection.baseline_id == bid)
                .order_by(BaselineSection.order_index)
            )
            for s in sections_result.scalars().all():
                items_result = await db.execute(
                    select(BaselineItem)
                    .where(BaselineItem.section_id == s.section_id)
                    .order_by(BaselineItem.order_index)
                )
                for i in items_result.scalars().all():
                    category_items[cat].append(BaselineItemOut(
                        item_id=i.item_id,
                        task_name=i.task_name,
                        instruction=i.instruction,
                        display_content=i.display_content,
                        expected_output=i.expected_output,
                        response_type=i.response_type,
                        target_phoneme=i.target_phoneme,
                        formula_weights=i.formula_weights,
                        fusion_weights=i.fusion_weights,
                        wpm_range=i.wpm_range,
                    ))

    # Apply 7-item cap balanced by category
    allocated = _allocate_items(category_items, BASELINE_ITEM_CAP)

    # Reconstruct output as a single synthetic assessment per category
    out: list[BaselineAssessmentOut] = []
    for cat, items in allocated.items():
        if not items:
            continue
        # Use the first assessment's metadata for the section container
        cat_assessments = category_assessments.get(cat, [])
        first_a = cat_assessments[0] if cat_assessments else None
        baseline_id = first_a.baseline_id if first_a else cat
        name = first_a.name if first_a else cat
        domain = first_a.domain if first_a else cat
        out.append(BaselineAssessmentOut(
            baseline_id=baseline_id,
            name=name,
            domain=domain,
            sections=[BaselineSectionOut(
                section_id=f"{baseline_id}-combined",
                section_name=f"{cat} Assessment",
                instructions=None,
                order_index=0,
                items=items,
            )],
        ))
    return out


@router.post("/submit", response_model=BaselineResultOut)
async def submit_baseline(
    body: BaselineSubmitRequest,
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    if not body.item_scores:
        raise HTTPException(400, "No item scores provided")
    avg_score = sum(s.score for s in body.item_scores) / len(body.item_scores)
    raw_score = int(avg_score)
    level = score_to_level(avg_score)
    result_id = uuid.uuid4()
    baseline_result = PatientBaselineResult(
        result_id=result_id,
        patient_id=patient.patient_id,
        baseline_id=body.baseline_id,
        therapist_id=patient.assigned_therapist_id,
        assessed_on=date.today().isoformat(),
        raw_score=raw_score,
        severity_rating=level,
    )
    db.add(baseline_result)
    await db.flush()
    for item_score in body.item_scores:
        db.add(BaselineItemResult(
            item_result_id=uuid.uuid4(),
            result_id=result_id,
            item_id=item_score.item_id,
            score_given=int(item_score.score),
        ))
    await db.commit()
    assessment = await db.get(BaselineAssessment, body.baseline_id)
    return BaselineResultOut(
        result_id=str(result_id),
        baseline_name=assessment.name if assessment else body.baseline_id,
        raw_score=raw_score,
        level=level,
        assessed_on=date.today().isoformat(),
    )


@router.get("/result", response_model=BaselineResultOut | None)
async def get_baseline_result(
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PatientBaselineResult)
        .where(PatientBaselineResult.patient_id == patient.patient_id)
        .order_by(PatientBaselineResult.assessed_on.desc())
    )
    br = result.scalar_one_or_none()
    if not br:
        return None
    assessment = await db.get(BaselineAssessment, br.baseline_id)
    return BaselineResultOut(
        result_id=str(br.result_id),
        baseline_name=assessment.name if assessment else br.baseline_id,
        raw_score=br.raw_score or 0,
        level=br.severity_rating or score_to_level(br.raw_score or 0),
        assessed_on=br.assessed_on,
    )


@router.get("/therapist-view/{patient_id}", response_model=BaselineResultOut | None)
async def therapist_get_baseline(
    patient_id: str,
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    patient = await db.get(Patient, patient_id)
    if not patient or patient.assigned_therapist_id != therapist.therapist_id:
        raise HTTPException(404, "Patient not found")
    result = await db.execute(
        select(PatientBaselineResult)
        .where(PatientBaselineResult.patient_id == patient_id)
        .order_by(PatientBaselineResult.assessed_on.desc())
    )
    br = result.scalar_one_or_none()
    if not br:
        return None
    assessment = await db.get(BaselineAssessment, br.baseline_id)
    return BaselineResultOut(
        result_id=str(br.result_id),
        baseline_name=assessment.name if assessment else br.baseline_id,
        raw_score=br.raw_score or 0,
        level=br.severity_rating or score_to_level(br.raw_score or 0),
        assessed_on=br.assessed_on,
    )
