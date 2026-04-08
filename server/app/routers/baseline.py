import os
import uuid
import aiofiles
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.auth import require_patient, require_therapist
from app.config import settings
from app.models.users import Patient, Therapist
from app.models.scoring import Session
from app.models.baseline import (
    BaselineAssessment, BaselineDefectMapping, BaselineSection,
    BaselineItem, PatientBaselineResult, BaselineItemResult, BaselineAttempt,
)
from app.schemas.baseline import (
    BaselineAssessmentOut, BaselineSectionOut, BaselineItemOut,
    BaselineResultOut, BaselineItemDetailOut,
)
from app.tasks.baseline_analysis import analyze_baseline_attempt

router = APIRouter()

BASELINE_ITEM_CAP = 7
EXCLUDED_FORMULA_MODES = {"clinician_rated"}


def score_to_level(score: float) -> str:
    if score >= 80:
        return "advanced"
    if score >= 70:
        return "intermediate"
    return "beginner"


@router.get("/exercises", response_model=list[BaselineAssessmentOut])
async def get_baseline_exercises(
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    if not patient.pre_assigned_defect_ids:
        raise HTTPException(400, "No defects assigned to patient")
    defect_ids = patient.pre_assigned_defect_ids.get("defect_ids", [])

    mapping_result = await db.execute(
        select(BaselineDefectMapping)
        .where(BaselineDefectMapping.defect_id.in_(defect_ids))
    )
    baseline_ids = list({m.baseline_id for m in mapping_result.scalars().all()})
    if not baseline_ids:
        raise HTTPException(404, "No baseline assessments found for assigned defects")

    assessments_result = await db.execute(
        select(BaselineAssessment).where(BaselineAssessment.baseline_id.in_(baseline_ids))
    )
    assessments = assessments_result.scalars().all()

    out: list[BaselineAssessmentOut] = []
    total_items = 0
    for assessment in assessments:
        if total_items >= BASELINE_ITEM_CAP:
            break
        sections_result = await db.execute(
            select(BaselineSection)
            .where(BaselineSection.baseline_id == assessment.baseline_id)
            .order_by(BaselineSection.order_index)
        )
        sections_out: list[BaselineSectionOut] = []
        for section in sections_result.scalars().all():
            if total_items >= BASELINE_ITEM_CAP:
                break
            items_result = await db.execute(
                select(BaselineItem)
                .where(
                    BaselineItem.section_id == section.section_id,
                    BaselineItem.formula_mode.notin_(EXCLUDED_FORMULA_MODES)
                    | BaselineItem.formula_mode.is_(None),
                )
                .order_by(BaselineItem.order_index)
            )
            items = items_result.scalars().all()
            remaining = BASELINE_ITEM_CAP - total_items
            items = items[:remaining]
            if not items:
                continue
            sections_out.append(BaselineSectionOut(
                section_id=section.section_id,
                section_name=section.section_name,
                instructions=section.instructions,
                order_index=section.order_index,
                items=[BaselineItemOut(
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
                ) for i in items],
            ))
            total_items += len(items)
        if sections_out:
            out.append(BaselineAssessmentOut(
                baseline_id=assessment.baseline_id,
                name=assessment.name,
                domain=assessment.domain,
                sections=sections_out,
            ))
    return out


@router.post("/start")
async def start_baseline_session(
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    """Create a baseline session. Returns session_id used for all subsequent baseline attempts."""
    session = Session(
        session_id=uuid.uuid4(),
        patient_id=patient.patient_id,
        therapist_id=patient.assigned_therapist_id,
        session_type="baseline",
    )
    db.add(session)
    await db.commit()
    return {"session_id": str(session.session_id)}


@router.post("/{session_id}/attempt")
async def submit_baseline_attempt(
    session_id: str,
    item_id: str = Form(...),
    audio: UploadFile = File(...),
    patient: Annotated[Patient, Depends(require_patient)] = None,
    db: AsyncSession = Depends(get_db),
):
    """Upload audio for one baseline item. Queues ML scoring asynchronously."""
    session = await db.get(Session, uuid.UUID(session_id))
    if not session or session.patient_id != patient.patient_id or session.session_type != "baseline":
        raise HTTPException(404, "Baseline session not found")

    item = await db.get(BaselineItem, item_id)
    if not item:
        raise HTTPException(404, "Baseline item not found")
    if item.formula_mode in EXCLUDED_FORMULA_MODES:
        raise HTTPException(400, "This baseline item requires clinician rating")

    ext = os.path.splitext(audio.filename or "audio.webm")[1] or ".webm"
    filename = f"baseline_{uuid.uuid4()}{ext}"
    filepath = os.path.join(settings.upload_dir, filename)
    os.makedirs(settings.upload_dir, exist_ok=True)
    async with aiofiles.open(filepath, "wb") as f:
        content = await audio.read()
        await f.write(content)

    attempt = BaselineAttempt(
        session_id=uuid.UUID(session_id),
        item_id=item_id,
        audio_file_path=filepath,
        result="pending",
    )
    db.add(attempt)
    await db.commit()

    analyze_baseline_attempt.delay(str(attempt.attempt_id))

    return {"attempt_id": str(attempt.attempt_id), "result": "pending"}


@router.get("/attempt/{attempt_id}")
async def poll_baseline_attempt(
    attempt_id: str,
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    """Poll the ML scoring result for a single baseline item attempt."""
    result = await db.execute(
        select(BaselineAttempt)
        .join(Session, BaselineAttempt.session_id == Session.session_id)
        .where(
            BaselineAttempt.attempt_id == uuid.UUID(attempt_id),
            Session.patient_id == patient.patient_id,
        )
    )
    attempt = result.scalar_one_or_none()
    if not attempt:
        raise HTTPException(404, "Baseline attempt not found")
    return {
        "attempt_id": attempt_id,
        "result": attempt.result,
        "computed_score": float(attempt.computed_score) if attempt.computed_score is not None else None,
        "phoneme_accuracy": float(attempt.ml_phoneme_accuracy) if attempt.ml_phoneme_accuracy is not None else None,
        "asr_transcript": attempt.asr_transcript,
    }


@router.post("/{session_id}/complete", response_model=BaselineResultOut)
async def complete_baseline_session(
    session_id: str,
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    """Aggregate all scored baseline attempts into patient_baseline_result and baseline_item_result rows."""
    session = await db.get(Session, uuid.UUID(session_id))
    if not session or session.patient_id != patient.patient_id or session.session_type != "baseline":
        raise HTTPException(404, "Baseline session not found")

    attempts_result = await db.execute(
        select(BaselineAttempt).where(
            BaselineAttempt.session_id == uuid.UUID(session_id),
            BaselineAttempt.result == "scored",
        )
    )
    scored_attempts = attempts_result.scalars().all()
    if not scored_attempts:
        raise HTTPException(400, "No scored baseline attempts found.")

    item_ids = [a.item_id for a in scored_attempts]
    items_result = await db.execute(
        select(BaselineItem).where(BaselineItem.item_id.in_(item_ids))
    )
    items_by_id = {i.item_id: i for i in items_result.scalars().all()}

    section_ids = list({i.section_id for i in items_by_id.values()})
    sections_result = await db.execute(
        select(BaselineSection).where(BaselineSection.section_id.in_(section_ids))
    )
    baseline_ids = list({s.baseline_id for s in sections_result.scalars().all()})
    primary_baseline_id = baseline_ids[0] if baseline_ids else "unknown"

    avg_score = sum(
        float(a.computed_score) for a in scored_attempts if a.computed_score is not None
    ) / len(scored_attempts)
    raw_score = int(round(avg_score))
    severity = score_to_level(avg_score)

    previous_results_result = await db.execute(
        select(PatientBaselineResult).where(PatientBaselineResult.patient_id == patient.patient_id)
    )
    previous_results = previous_results_result.scalars().all()
    for previous_result in previous_results:
        previous_items_result = await db.execute(
            select(BaselineItemResult).where(BaselineItemResult.result_id == previous_result.result_id)
        )
        for previous_item in previous_items_result.scalars().all():
            await db.delete(previous_item)
        await db.delete(previous_result)
    await db.flush()

    result_id = uuid.uuid4()
    baseline_result = PatientBaselineResult(
        result_id=result_id,
        patient_id=patient.patient_id,
        baseline_id=primary_baseline_id,
        therapist_id=patient.assigned_therapist_id,
        assessed_on=date.today(),
        raw_score=raw_score,
        severity_rating=severity,
    )
    db.add(baseline_result)
    await db.flush()

    for attempt in scored_attempts:
        db.add(BaselineItemResult(
            item_result_id=uuid.uuid4(),
            result_id=result_id,
            item_id=attempt.item_id,
            score_given=int(round(float(attempt.computed_score or 0))),
        ))

    await db.commit()
    assessment = await db.get(BaselineAssessment, primary_baseline_id)
    return BaselineResultOut(
        result_id=str(result_id),
        baseline_name=assessment.name if assessment else primary_baseline_id,
        raw_score=raw_score,
        level=severity,
        assessed_on=date.today(),
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
        .limit(1)
    )
    br = result.scalars().first()
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
        .limit(1)
    )
    br = result.scalars().first()
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


@router.get("/therapist-view/{patient_id}/items", response_model=list[BaselineItemDetailOut])
async def therapist_get_baseline_items(
    patient_id: str,
    therapist: Annotated[Therapist, Depends(require_therapist)],
    db: AsyncSession = Depends(get_db),
):
    """Return item-level data for the patient's latest completed baseline result."""
    patient = await db.get(Patient, patient_id)
    if not patient or patient.assigned_therapist_id != therapist.therapist_id:
        raise HTTPException(404, "Patient not found")

    result_result = await db.execute(
        select(PatientBaselineResult)
        .where(PatientBaselineResult.patient_id == patient.patient_id)
        .order_by(PatientBaselineResult.assessed_on.desc())
        .limit(1)
    )
    baseline_result = result_result.scalars().first()
    if not baseline_result:
        return []

    items_result = await db.execute(
        select(BaselineItemResult, BaselineItem)
        .join(BaselineItem, BaselineItemResult.item_id == BaselineItem.item_id)
        .where(BaselineItemResult.result_id == baseline_result.result_id)
        .order_by(BaselineItem.order_index)
    )
    rows = items_result.all()
    return [
        BaselineItemDetailOut(
            item_id=item.item_id,
            prompt_text=item.instruction or item.display_content,
            transcript=None,
            phoneme_accuracy=None,
            fluency_score=None,
            final_score=float(item_result.score_given) if item_result.score_given is not None else 0.0,
            pass_fail=(float(item_result.score_given) >= 70) if item_result.score_given is not None else False,
            created_at=baseline_result.assessed_on.isoformat(),
        )
        for item_result, item in rows
    ]
