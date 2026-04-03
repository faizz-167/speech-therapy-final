import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routers import auth, therapist, plans, patient, baseline, session, progress

os.makedirs(settings.upload_dir, exist_ok=True)

app = FastAPI(title="SpeechPath API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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

@app.get("/health")
async def health():
    return {"status": "ok"}
