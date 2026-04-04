import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.auth import require_patient
from app.models.users import Patient
from app.models.baseline import (
    BaselineAssessment, BaselineDefectMapping, BaselineSection,
    BaselineItem, PatientBaselineResult, BaselineItemResult,
)
from app.schemas.baseline import (
    BaselineAssessmentOut, BaselineSectionOut, BaselineItemOut,
    BaselineSubmitRequest, BaselineResultOut,
)

router = APIRouter()


def score_to_level(score: float) -> str:
    if score >= 80:
        return "advanced"
    elif score >= 70:
        return "medium"
    return "easy"


@router.get("/exercises", response_model=list[BaselineAssessmentOut])
async def get_baseline_exercises(
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    if not patient.pre_assigned_defect_ids:
        raise HTTPException(400, "No defects assigned to patient")
    defect_ids = patient.pre_assigned_defect_ids.get("defect_ids", [])
    mapping_result = await db.execute(
        select(BaselineDefectMapping.baseline_id)
        .where(BaselineDefectMapping.defect_id.in_(defect_ids))
        .distinct()
    )
    baseline_ids = [row[0] for row in mapping_result.fetchall()]
    if not baseline_ids:
        raise HTTPException(404, "No baseline assessments found for assigned defects")
    result = await db.execute(
        select(BaselineAssessment).where(BaselineAssessment.baseline_id.in_(baseline_ids))
    )
    assessments = result.scalars().all()
    out = []
    for a in assessments:
        sections_result = await db.execute(
            select(BaselineSection)
            .where(BaselineSection.baseline_id == a.baseline_id)
            .order_by(BaselineSection.order_index)
        )
        sections = sections_result.scalars().all()
        section_outs = []
        for s in sections:
            items_result = await db.execute(
                select(BaselineItem)
                .where(BaselineItem.section_id == s.section_id)
                .order_by(BaselineItem.order_index)
            )
            items = items_result.scalars().all()
            section_outs.append(BaselineSectionOut(
                section_id=s.section_id,
                section_name=s.section_name,
                instructions=s.instructions,
                order_index=s.order_index,
                items=[
                    BaselineItemOut(
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
                    )
                    for i in items
                ],
            ))
        out.append(BaselineAssessmentOut(
            baseline_id=a.baseline_id,
            name=a.name,
            domain=a.domain,
            sections=section_outs,
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
    db: AsyncSession = Depends(get_db),
):
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
