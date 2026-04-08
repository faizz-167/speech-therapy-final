import asyncio
import json
import os
import app.models  # noqa: F401
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
import redis.asyncio as aioredis
from app.auth import COOKIE_NAME, decode_token
from app.config import settings
from app.database import Base, engine
from app.routers import auth, therapist, plans, patient, baseline, session, progress

os.makedirs(settings.upload_dir, exist_ok=True)

app = FastAPI(title="SpeechPath API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(therapist.router, prefix="/therapist", tags=["therapist"])
app.include_router(plans.router, prefix="/plans", tags=["plans"])
app.include_router(patient.router, prefix="/patient", tags=["patient"])
app.include_router(baseline.router, prefix="/baseline", tags=["baseline"])
app.include_router(session.router, prefix="/session", tags=["session"])
app.include_router(progress.router, prefix="", tags=["progress"])


@app.on_event("startup")
async def ensure_schema_tables() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.exec_driver_sql(
            "ALTER TABLE IF EXISTS baseline_attempt "
            "ADD COLUMN IF NOT EXISTS ml_speech_rate_score NUMERIC"
        )
        await conn.exec_driver_sql(
            "ALTER TABLE IF EXISTS baseline_attempt "
            "ADD COLUMN IF NOT EXISTS dominant_emotion VARCHAR"
        )
        await conn.exec_driver_sql(
            "ALTER TABLE IF EXISTS baseline_attempt "
            "ADD COLUMN IF NOT EXISTS emotion_score NUMERIC"
        )
        await conn.exec_driver_sql(
            "ALTER TABLE IF EXISTS baseline_attempt "
            "ADD COLUMN IF NOT EXISTS engagement_score NUMERIC"
        )
        await conn.exec_driver_sql(
            "ALTER TABLE IF EXISTS patient_baseline_result "
            "ADD COLUMN IF NOT EXISTS session_id UUID"
        )

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.websocket("/ws/{patient_id}")
async def websocket_endpoint(websocket: WebSocket, patient_id: str):
    await websocket.accept()
    token = websocket.cookies.get(COOKIE_NAME)
    if not token:
        # Fall back to explicit auth message for the current browser tab session.
        try:
            auth_msg = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
        except (asyncio.TimeoutError, Exception):
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        token = auth_msg.get("token") if isinstance(auth_msg, dict) else None
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    try:
        payload = decode_token(token)
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    if payload.get("role") != "patient" or payload.get("sub") != patient_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    r = aioredis.from_url(settings.redis_url)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"ws:patient:{patient_id}")
    ping_task = None
    try:
        async def send_pings():
            while True:
                await asyncio.sleep(30)
                await websocket.send_json({"type": "ping"})

        ping_task = asyncio.create_task(send_pings())
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await websocket.send_json(data)
    except WebSocketDisconnect:
        pass
    finally:
        if ping_task:
            ping_task.cancel()
        await pubsub.unsubscribe()
        await r.aclose()
