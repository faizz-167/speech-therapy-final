# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SpeechPath** — a clinical speech therapy platform with two user roles: Therapist and Patient. Therapists create therapy plans; patients complete audio recording tasks that are ML-scored in real time via WebSockets.

## Running the Project

Three terminals required for full dev environment.

### Terminal 1 — FastAPI backend
```bash
cd server
venv\Scripts\activate          # Windows
uvicorn app.main:app --reload
```

### Terminal 2 — Celery worker (Windows requires `--pool=solo`)
```bash
cd server
venv\Scripts\activate
celery -A app.celery_app worker --pool=solo --loglevel=info
```

### Terminal 3 — Next.js frontend
```bash
cd client
npm run dev
```

### Redis (Docker)
```bash
docker compose -f docker-compose.redis.yml up -d
```

### Database reset/seed (destructive — dev only)
```bash
cd server
python reset_db.py   # drops and recreates all tables
python seed_data.py  # seeds clinical content
```

## Environment Variables

**`server/.env`**
```
DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/speechpath"
DATABASE_URL_SYNC="postgresql://user:password@localhost:5432/speechpath"
REDIS_URL="redis://localhost:6379/0"
SECRET_KEY="..."
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=10080
UPLOAD_DIR="uploads"
CORS_ORIGINS='["http://localhost:3000"]'
```

**`client/.env.local`**
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

## Python Setup

Use Python 3.13. Install with build constraints due to `openai-whisper` compatibility:
```bash
pip install --build-constraint build-constraints.txt -r requirements.txt
```

## Architecture

### Backend (`server/app/`)
- **FastAPI** app with async SQLAlchemy + asyncpg (PostgreSQL)
- **Celery** + Redis handles all ML-heavy async tasks (Whisper transcription, forced phoneme alignment, emotion classification)
- **WebSocket** endpoint at `/ws/{patient_id}` — authenticates via JWT cookie or first message token, subscribes to Redis pub/sub channel `ws:patient:{patient_id}`, forwards `score_ready` events to the browser
- Schema migrations are applied inline at startup via `ALTER TABLE IF EXISTS` in `main.py`'s `startup` event — no Alembic migrations folder

**Router layout:**
| Prefix | File | Purpose |
|--------|------|---------|
| `/auth` | `routers/auth.py` | Login, register (therapist/patient) |
| `/therapist` | `routers/therapist.py` | Patient management, approval codes |
| `/plans` | `routers/plans.py` | Therapy plan CRUD + auto-regeneration |
| `/patient` | `routers/patient.py` | Patient tasks, submissions, escalation |
| `/baseline` | `routers/baseline.py` | Baseline assessment flow |
| `/session` | `routers/session.py` | Session guards |
| `` | `routers/progress.py` | Progress/metrics endpoints |

**ML pipeline (`tasks/analysis.py`):** Celery task triggered on audio submission → Whisper ASR → forced phoneme alignment → SpeechBrain/Wav2Vec2 emotion classification → scoring engine → publishes result to Redis → WS delivers to client.

**Scoring (`scoring/engine.py`):** Weighted composite score from phoneme accuracy (PA), word accuracy (WA), fluency score (FS), speech rate score (SRS), and confidence score (CS), fused with an engagement score (emotion). Adaptive thresholds: advance ≥75, stay 60–74, drop <60.

### Frontend (`client/`)
- **Next.js 16** App Router with TypeScript
- **Zustand** for auth state (`store/auth.ts`)
- **TanStack Query** for server state
- `client/lib/api.ts` — central fetch wrapper; attaches JWT from Zustand store, handles 401/403 with registered `onAuthExpired` callback
- `client/lib/ws.ts` — `createWebSocket()` factory; auto-reconnects up to 5× with 2s delay; sends token as first WS message

**Route layout:**
- `/` — landing/login
- `/patient/home` — task dashboard with notifications
- `/patient/tasks` — task list
- `/patient/tasks/[assignmentId]` — audio recording + real-time scoring
- `/patient/progress` — progress charts
- `/patient/baseline` — baseline assessment
- `/therapist/dashboard` — patient list
- `/therapist/patients/[id]/plan` — plan editor

**Type definitions** are in `client/types/` split by domain: `auth`, `patient`, `therapist`, `plans`, `session`, `baseline`, `progress`.
