import os
import uuid
import aiofiles
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Annotated
from app.database import get_db
from app.auth import require_patient
from app.models.users import Patient
from app.models.scoring import Session, SessionPromptAttempt, AttemptScoreDetail
from app.schemas.session import StartSessionRequest, AttemptStatusResponse
from app.tasks.analysis import analyze_attempt
from app.config import settings

router = APIRouter()


@router.post("/start")
async def start_session(
    body: StartSessionRequest,
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    session = Session(
        session_id=uuid.uuid4(),
        patient_id=patient.patient_id,
        therapist_id=patient.assigned_therapist_id,
        plan_id=uuid.UUID(body.plan_id) if body.plan_id else None,
        session_type="therapy",
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
    audio: UploadFile = File(...),
    patient: Annotated[Patient, Depends(require_patient)] = None,
    db: AsyncSession = Depends(get_db),
):
    ext = os.path.splitext(audio.filename or "audio.webm")[1] or ".webm"
    filename = f"{uuid.uuid4()}{ext}"
    filepath = os.path.join(settings.upload_dir, filename)
    os.makedirs(settings.upload_dir, exist_ok=True)
    async with aiofiles.open(filepath, "wb") as f:
        content = await audio.read()
        await f.write(content)

    attempt = SessionPromptAttempt(
        attempt_id=uuid.uuid4(),
        session_id=uuid.UUID(session_id),
        prompt_id=prompt_id,
        task_mode=task_mode,
        prompt_type=prompt_type,
        audio_file_path=filepath,
        result="pending",
        mic_activated_at=datetime.now(timezone.utc),
    )
    db.add(attempt)
    await db.commit()

    analyze_attempt.delay(str(attempt.attempt_id))

    return {"attempt_id": str(attempt.attempt_id), "result": "pending"}


@router.get("/attempt/{attempt_id}", response_model=AttemptStatusResponse)
async def poll_attempt(
    attempt_id: str,
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SessionPromptAttempt).where(SessionPromptAttempt.attempt_id == attempt_id)
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
                "word_accuracy": float(detail.word_accuracy or 0),
                "phoneme_accuracy": float(detail.phoneme_accuracy or 0),
                "fluency_score": float(detail.fluency_score or 0),
                "speech_rate_wpm": detail.speech_rate_wpm,
                "final_score": float(detail.final_score or 0),
                "pass_fail": detail.pass_fail,
                "adaptive_decision": detail.adaptive_decision,
                "dominant_emotion": detail.dominant_emotion,
                "asr_transcript": detail.asr_transcript,
            }
    return AttemptStatusResponse(attempt_id=attempt_id, result=attempt.result, score=score)


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Session).where(Session.session_id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")
    return {
        "session_id": str(session.session_id),
        "session_date": str(session.session_date),
        "session_type": session.session_type,
    }
