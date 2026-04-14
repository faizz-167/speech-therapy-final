import os
import uuid
import aiofiles
from datetime import date, datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from typing import Annotated
from app.database import get_db
from app.auth import require_patient
from app.models.users import Patient
from app.models.content import Prompt
from app.models.scoring import Session, SessionPromptAttempt, AttemptScoreDetail
from app.models.operations import AudioFile
from app.models.plan import TherapyPlan, PlanTaskAssignment
from app.schemas.session import StartSessionRequest, AttemptStatusResponse
from app.tasks.analysis import analyze_attempt
from app.config import settings
from app.utils.session_notes import default_session_notes, parse_session_notes, serialize_session_notes

router = APIRouter()


def _parse_browser_datetime(value: str, field_name: str) -> datetime:
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise HTTPException(400, f"Invalid {field_name}") from exc


@router.post("/start")
async def start_session(
    body: StartSessionRequest,
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    resolved_plan_id = None
    assignment: PlanTaskAssignment | None = None
    if body.assignment_id:
        assignment = await db.get(PlanTaskAssignment, body.assignment_id)
        if not assignment:
            raise HTTPException(404, "Assignment not found")
        plan = await db.get(TherapyPlan, assignment.plan_id)
        if not plan or plan.patient_id != patient.patient_id:
            raise HTTPException(404, "Assignment not found")
        if plan.status != "approved":
            raise HTTPException(403, "Plan is not approved")
        resolved_plan_id = assignment.plan_id
        existing_result = await db.execute(
            select(Session).where(
                Session.patient_id == patient.patient_id,
                Session.plan_id == resolved_plan_id,
                Session.session_type == "therapy",
            ).order_by(Session.session_date.desc())
        )
        for existing_session in existing_result.scalars().all():
            notes = parse_session_notes(existing_session.session_notes)
            if notes.get("assignment_id") == body.assignment_id and not notes.get("completed"):
                if notes.get("escalated"):
                    raise HTTPException(
                        status_code=403,
                        detail="Session locked — this task requires therapist review before you can continue.",
                    )
                return {"session_id": str(existing_session.session_id)}
    elif body.plan_id:
        plan = await db.get(TherapyPlan, uuid.UUID(body.plan_id))
        if not plan or plan.patient_id != patient.patient_id:
            raise HTTPException(404, "Plan not found")
        if plan.status != "approved":
            raise HTTPException(403, "Plan is not approved")
        resolved_plan_id = plan.plan_id
    else:
        raise HTTPException(400, "assignment_id or plan_id is required")

    today = date.today()
    today_sessions_result = await db.execute(
        select(Session).where(
            Session.patient_id == patient.patient_id,
            Session.session_type == "therapy",
            func.date(Session.session_date) == today,
        )
    )
    for sess in today_sessions_result.scalars().all():
        sess_notes = parse_session_notes(sess.session_notes)
        if sess_notes.get("escalated"):
            raise HTTPException(
                status_code=403,
                detail="Session locked — one of today's tasks requires therapist review before you can continue.",
            )

    session = Session(
        session_id=uuid.uuid4(),
        patient_id=patient.patient_id,
        therapist_id=patient.assigned_therapist_id,
        plan_id=resolved_plan_id,
        session_type="therapy",
        session_notes=serialize_session_notes(
            default_session_notes(
                assignment_id=body.assignment_id,
                task_id=assignment.task_id if body.assignment_id and assignment else None,
            )
        ),
    )
    db.add(session)
    await db.commit()
    return {"session_id": str(session.session_id)}


@router.post("/{session_id}/attempt")
async def submit_attempt(
    session_id: str,
    prompt_id: str = Form(...),
    task_mode: str = Form(...),
    prompt_type: str = Form("exercise"),
    mic_activated_at: str | None = Form(None),
    speech_start_at: str | None = Form(None),
    audio: UploadFile = File(...),
    patient: Annotated[Patient, Depends(require_patient)] = None,
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(Session, session_id)
    if not session or session.patient_id != patient.patient_id:
        raise HTTPException(404, "Session not found")

    attempt_notes = parse_session_notes(session.session_notes)
    if attempt_notes.get("escalated"):
        raise HTTPException(
            status_code=403,
            detail="This session is locked pending therapist review.",
        )

    prompt = await db.get(Prompt, prompt_id)
    if not prompt:
        raise HTTPException(404, "Prompt not found")
    if prompt.task_mode != task_mode or prompt.prompt_type != prompt_type:
        raise HTTPException(400, "Prompt metadata mismatch")

    parsed_mic_at = None
    parsed_speech_at = None
    if mic_activated_at:
        parsed_mic_at = _parse_browser_datetime(mic_activated_at, "mic_activated_at")
    if speech_start_at:
        parsed_speech_at = _parse_browser_datetime(speech_start_at, "speech_start_at")

    attempt_count_result = await db.execute(
        select(func.count(SessionPromptAttempt.attempt_id)).where(
            SessionPromptAttempt.session_id == session.session_id,
            SessionPromptAttempt.prompt_id == prompt_id,
        )
    )
    attempt_number = int(attempt_count_result.scalar() or 0) + 1
    if attempt_number > 3:
        raise HTTPException(400, "Maximum attempts reached for this exercise")

    ext = os.path.splitext(audio.filename or "audio.webm")[1] or ".webm"
    filename = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join(settings.upload_dir, filename)
    os.makedirs(settings.upload_dir, exist_ok=True)
    async with aiofiles.open(filepath, "wb") as f:
        content = await audio.read()
        await f.write(content)

    file_size = len(content)
    ext_mime = "audio/webm" if ext == ".webm" else "audio/wav"

    attempt = SessionPromptAttempt(
        attempt_id=uuid.uuid4(),
        session_id=session.session_id,
        prompt_id=prompt_id,
        attempt_number=attempt_number,
        task_mode=task_mode,
        prompt_type=prompt_type,
        audio_file_path=filepath,
        result="pending",
        mic_activated_at=parsed_mic_at or datetime.now(timezone.utc),
        speech_start_at=parsed_speech_at,
    )
    db.add(attempt)
    await db.commit()

    audio_file = AudioFile(
        patient_id=patient.patient_id,
        session_id=session.session_id,
        attempt_id=attempt.attempt_id,
        file_path=filepath,
        file_size_bytes=file_size,
        mime_type=ext_mime,
    )
    db.add(audio_file)
    await db.commit()

    analyze_attempt.delay(str(attempt.attempt_id))

    return {
        "attempt_id": str(attempt.attempt_id),
        "attempt_number": attempt_number,
        "result": "pending",
    }


@router.get("/attempt/{attempt_id}", response_model=AttemptStatusResponse)
async def poll_attempt(
    attempt_id: str,
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SessionPromptAttempt)
        .join(Session, SessionPromptAttempt.session_id == Session.session_id)
        .where(
            SessionPromptAttempt.attempt_id == attempt_id,
            Session.patient_id == patient.patient_id,
        )
    )
    attempt = result.scalar_one_or_none()
    if not attempt:
        raise HTTPException(404, "Attempt not found")
    score = None
    if attempt.result and attempt.result != "pending":
        score_result = await db.execute(
            select(AttemptScoreDetail).where(AttemptScoreDetail.attempt_id == attempt_id)
        )
        detail = score_result.scalar_one_or_none()
        if detail:
            score = {
                "attempt_number": attempt.attempt_number,
                "word_accuracy": float(detail.word_accuracy) if detail.word_accuracy is not None else None,
                "phoneme_accuracy": float(detail.phoneme_accuracy) if detail.phoneme_accuracy is not None else None,
                "pa_available": bool(detail.pa_available) if detail.pa_available is not None else None,
                "fluency_score": float(detail.fluency_score or 0),
                "speech_rate_wpm": detail.speech_rate_wpm,
                "speech_rate_score": float(detail.speech_rate_score or 0),
                "confidence_score": float(detail.confidence_score or 0),
                "behavioral_score": float(detail.behavioral_score or 0),
                "emotion_score": float(detail.emotion_score or 0),
                "engagement_score": float(detail.engagement_score or 0),
                "speech_score": float(detail.speech_score or 0),
                "final_score": float(detail.final_score or 0),
                "pass_fail": detail.pass_fail,
                "adaptive_decision": detail.adaptive_decision,
                "dominant_emotion": detail.dominant_emotion,
                "asr_transcript": detail.asr_transcript,
                "performance_level": detail.performance_level,
                "review_recommended": bool(detail.review_recommended),
                "fail_reason": detail.fail_reason,
            }
    return AttemptStatusResponse(attempt_id=attempt_id, result=attempt.result, score=score)


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Session).where(
            Session.session_id == session_id,
            Session.patient_id == patient.patient_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")
    return {
        "session_id": str(session.session_id),
        "session_date": str(session.session_date),
        "session_type": session.session_type,
    }
