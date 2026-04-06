# SpeechPath — Project Context

> Single source of truth for AI assistants and developers. Last updated: 2026-04-05.

---

## Project Overview

**SpeechPath** is a full-stack, AI-powered speech therapy platform with two roles:

- **Therapist:** Manages patients, generates weekly AI therapy plans, reviews performance
- **Patient:** Completes voice exercises, receives real-time ML-scored feedback, tracks progress

Core idea: automate the scoring workload of speech therapists using ASR, phoneme alignment, disfluency detection, and emotion recognition — all orchestrated via async Celery tasks with WebSocket delivery.

---

## Architecture

```
Browser (Next.js)
   │
   ├── REST API (FastAPI)          → auth, plans, sessions, progress
   │     ├── Routers               → request handling + DB access
   │     ├── Services              → plan generation logic
   │     └── Celery task           → async ML scoring pipeline
   │
   ├── WebSocket (FastAPI /ws)     → real-time score delivery to patient
   │
   ├── Redis                       → Celery broker + pub/sub bus
   │
   ├── PostgreSQL (Neon)           → all persistent data (SQLAlchemy async)
   │
   └── ML Models (on worker)
         ├── Whisper ASR           → transcript + word timestamps + confidence
         ├── HuBERT Phoneme        → phoneme accuracy via forced alignment
         ├── spaCy NLP             → disfluency rate, pause score, fluency score
         └── SpeechBrain Emotion   → dominant emotion + engagement score
```

**Key interaction flow:**
Patient records audio → POST /session/{id}/attempt → Celery task fires → ML pipeline runs → score saved → Redis pub/sub → WebSocket → client displays result

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16.2.2, React 19, TypeScript 5, Tailwind CSS v4 |
| State | Zustand 5 with localStorage persistence |
| UI Components | Custom Neo* components (`NeoButton`, `NeoCard`, `NeoInput`) |
| Drag & Drop | @dnd-kit/core, @dnd-kit/sortable (Kanban plan editor) |
| Charts | Recharts 3.8.1 |
| Backend | FastAPI 0.115, Uvicorn |
| ORM | SQLAlchemy 2.0 async (asyncpg driver) |
| Sync ORM | psycopg2-binary (Celery workers only) |
| Database | Neon PostgreSQL (hosted, fully seeded, no migrations pending) |
| Auth | JWT via python-jose (HS256, 7-day expiry) + bcrypt/passlib |
| Task Queue | Celery 5.4 |
| Message Broker | Redis (local) |
| Real-time | FastAPI WebSocket + Redis pub/sub |
| ASR | OpenAI Whisper (`whisper-small`, GPU preferred) |
| Phoneme | torchaudio HuBERT MMS_FA forced alignment |
| NLP | spaCy `en_core_web_lg` |
| Emotion | SpeechBrain `emotion-recognition-wav2vec2-IEMOCAP` |

---

## Core Features

1. **Registration & Approval**
   - Therapist registers → gets unique 8-char code
   - Patient registers with therapist code → status = `pending`
   - Therapist approves → status = `approved` → patient gains access

2. **Baseline Assessment**
   - Patient completes structured voice exercises mapped to their defects
   - AI scores baseline → determines starting difficulty level

3. **AI Therapy Plan Generation**
   - `services/plan_generator.py` selects tasks based on patient defects + baseline level
   - Produces 7-day plan (14 assignments, 2/day) → status = `draft`
   - Therapist reviews/edits via Kanban → approves → status = `approved`

4. **Real-Time Exercise Scoring**
   - Patient records audio for a prompt
   - Audio uploaded + Celery task queued
   - ML pipeline (ASR → phoneme → disfluency → emotion) runs on worker
   - Score saved, published via Redis → WebSocket delivers to patient

5. **Adaptive Difficulty**
   - Final score ≥ 75 → advance; 55–74 → stay; < 55 → drop level
   - All thresholds configurable per task via `TaskScoringWeights`

6. **Progress Tracking**
   - `PatientTaskProgress`: per-task level, consecutive passes/fails
   - `SessionEmotionSummary`: per-session emotion trends
   - Patient dashboard: accuracy, emotion, performance over time

---

## Data Flow

```
1. Auth
   POST /auth/login → JWT stored in Zustand (localStorage)
   All subsequent requests: Authorization: Bearer <token>

2. Exercise Session
   Patient selects task → POST /session/start → session_id
   For each prompt:
     a. Patient records → Blob → POST /session/{id}/attempt (multipart)
     b. Server saves audio to uploads/, queues Celery task
     c. Celery worker:
        - Loads audio
        - whisper_asr.transcribe() → transcript + confidence
        - hubert_phoneme.align_phonemes() → phoneme accuracy
        - spacy_disfluency.score_disfluency() → fluency metrics
        - speechbrain_emotion.classify_emotion() → emotion + engagement
        - scoring/engine.score_attempt() → final_score + adaptive_decision
        - INSERT AttemptScoreDetail
        - UPDATE SessionPromptAttempt.result
        - PUBLISH to Redis: ws:patient:{patient_id}
     d. WebSocket relays message to patient browser
     e. Client renders ScoreDisplay with all metrics

3. Plan Management
   Therapist: POST /plans/generate → draft plan created
   Therapist edits via Kanban → PUT /plans/{id}/assignments
   Therapist: POST /plans/{id}/approve → status = approved
   Patient: GET /patient/tasks → sees today's assignments
```

---

## Key Files & Structure

```
sppech-therapy-final/
├── server/app/
│   ├── main.py                  # FastAPI app, CORS, router registration, WebSocket /ws/{patient_id}
│   ├── config.py                # Pydantic Settings (reads .env)
│   ├── database.py              # Async SQLAlchemy engine + get_db dependency
│   ├── auth.py                  # JWT encode/decode, require_therapist(), require_patient()
│   ├── celery_app.py            # Celery instance, Redis broker/backend config
│   ├── models/
│   │   ├── users.py             # Therapist, Patient, PatientStatus
│   │   ├── content.py           # Defect, Task, TaskLevel, Prompt (merged: speech_target,
│   │   │                        #   evaluation_target, feedback_rule, prompt_scoring),
│   │   │                        #   TaskDefectMapping, TaskScoringWeights,
│   │   │                        #   AdaptiveThreshold, DefectPAThreshold, EmotionWeightsConfig
│   │   ├── baseline.py          # BaselineAssessment, BaselineDefectMapping, BaselineSection,
│   │   │                        #   BaselineItem, PatientBaselineResult, BaselineItemResult
│   │   ├── plan.py              # TherapyPlan, PlanTaskAssignment, PlanRevisionHistory
│   │   ├── scoring.py           # Session, SessionPromptAttempt, AttemptScoreDetail,
│   │   │                        #   PatientTaskProgress, SessionEmotionSummary
│   │   └── operations.py        # AudioFile, TherapistNotification
│   ├── routers/
│   │   ├── auth.py              # /auth/register/therapist|patient, /auth/login, /auth/me
│   │   ├── therapist.py         # /therapist/profile|dashboard|patients
│   │   ├── plans.py             # /plans/* (generate, CRUD, assignments)
│   │   ├── patient.py           # /patient/profile|plans|tasks|progress
│   │   ├── baseline.py          # /baseline/* (assessments, attempts, results)
│   │   ├── session.py           # /session/start, attempt submission, polling
│   │   └── progress.py          # /progress, /progress/emotion-summary
│   ├── services/
│   │   └── plan_generator.py    # generate_weekly_plan() — AI plan creation logic
│   ├── tasks/
│   │   └── analysis.py          # Celery task: analyze_attempt — full ML scoring pipeline
│   ├── ml/
│   │   ├── whisper_asr.py       # transcribe(path) → transcript, words, duration, confidence
│   │   ├── hubert_phoneme.py    # align_phonemes(path, transcript) → phoneme_accuracy
│   │   ├── spacy_disfluency.py  # score_disfluency(transcript, duration) → disfluency metrics
│   │   └── speechbrain_emotion.py # classify_emotion(path) → emotion, scores
│   └── scoring/
│       └── engine.py            # score_attempt() — formula v2, rules, adaptive decisions
│
├── client/
│   ├── app/
│   │   ├── login/               # Login page (both roles)
│   │   ├── patient/
│   │   │   ├── home/            # Dashboard
│   │   │   ├── baseline/        # Baseline exercise flow
│   │   │   ├── tasks/           # Task list + [assignmentId] exercise page
│   │   │   ├── progress/        # Progress charts
│   │   │   └── profile/
│   │   └── therapist/
│   │       ├── dashboard/       # Overview + pending approvals
│   │       ├── patients/        # Patient list + [id] detail
│   │       ├── plans/           # Plan editor (Kanban) + [patientId]
│   │       └── profile/
│   ├── components/
│   │   ├── ui/                  # NeoButton, NeoCard, NeoInput, NeoSelect
│   │   ├── patient/             # Recorder.tsx, ScoreDisplay.tsx, PatientNav.tsx
│   │   └── therapist/           # KanbanBoard.tsx, PatientCard.tsx, TherapistNav.tsx
│   ├── lib/
│   │   ├── api.ts               # REST client: get/post/patch/delete/upload
│   │   └── ws.ts                # WebSocket factory: createWebSocket(patientId, onScore)
│   ├── store/
│   │   └── auth.ts              # Zustand: token, role, userId, fullName, hydrated
│   └── types/index.ts           # All TypeScript interfaces
│
├── context.md                   # ← This file
└── docs/superpowers/            # Product specs and build plans
```

---

## APIs & Integrations

### REST Endpoints (prefix: `http://localhost:8000`)

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | /auth/register/therapist | — | Create therapist account |
| POST | /auth/register/patient | — | Create patient (requires therapist_code) |
| POST | /auth/login | — | Returns JWT token |
| GET | /auth/me | Any | Current user profile |
| GET | /therapist/dashboard | Therapist | Stats + pending patients |
| GET | /therapist/patients | Therapist | Patient list |
| POST | /therapist/patients/{id}/approve | Therapist | Approve patient |
| POST | /plans/generate | Therapist | Generate weekly plan |
| GET | /plans/patient/{id}/current | Therapist | Active plan |
| PUT | /plans/{id} | Therapist | Update plan |
| POST | /plans/{id}/approve | Therapist | Activate plan |
| POST | /session/start | Patient | Start exercise session |
| POST | /session/{id}/attempt | Patient | Submit audio attempt |
| GET | /session/attempt/{id} | Patient | Poll attempt score status |
| GET | /patient/tasks | Patient | Today's assignments |
| GET | /progress | Patient | Progress metrics |
| WS | /ws/{patient_id} | Patient (via auth msg) | Real-time score delivery |

### WebSocket Protocol
```
Connect → Send {"type":"auth","token":"<jwt>"} within 10s
Receive  {"type":"ping"}                          every 30s (keep-alive)
Receive  {"type":"score_ready", ...score_data}    after Celery task completes
```

### External Services
- **Neon PostgreSQL** — managed Postgres, connection via `DATABASE_URL`
- **Redis** — local, Celery broker + WebSocket pub/sub bus
- **OpenAI Whisper** — runs locally on worker (no API calls)
- **HuBERT / SpeechBrain** — local models (downloaded on first run to `~/.cache`)

---

## Environment & Setup

### Backend
```bash
cd server
python -m venv venv && source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python -m spacy download en_core_web_lg           # NLP model
cp .env.example .env                              # Fill in values

# Terminal 1: API server
uvicorn app.main:app --reload --port 8000

# Terminal 2: Celery worker
celery -A app.celery_app.celery_app worker --loglevel=info -P solo  # solo on Windows
```

### Frontend
```bash
cd client
npm install
cp .env.local.example .env.local                  # Fill in values
npm run dev                                        # http://localhost:3000
```

### Required Environment Variables

**server/.env**
```env
DATABASE_URL=postgresql+asyncpg://<user>:<pass>@<host>/<db>
DATABASE_URL_SYNC=postgresql://<user>:<pass>@<host>/<db>
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=<long-random-string>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080
UPLOAD_DIR=uploads
DEBUG=true
```

**client/.env.local**
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

---

## Scoring Formula v2

```
Speech Score    = PA*0.40 + WA*0.30 + FS*0.15 + SRS*0.10 + CS*0.05
Behavioral Score = RL*0.40 + TC*0.35 + AQ*0.25
Engagement Score = Emotion*0.65 + Behavioral*0.35
Final Score      = Speech*0.90 + Engagement*0.10

Rules applied post-composite:
  PA < 35       → cap Final at 45
  Engagement < 35 → Final -= 5
  Engagement > 85 → Final += 5

Adaptive:
  Final ≥ 75 → advance
  55–74      → stay
  < 55       → drop
```

Components: PA=phoneme accuracy, WA=word accuracy, FS=fluency score, SRS=speech rate score,
CS=confidence score, RL=response latency, TC=task completion, AQ=attempt quality

---

## Current Status

### Completed
- Full auth system (JWT, roles, patient approval flow)
- All DB models + 27-table schema redesigned (v2.0) — fresh empty database
- All 9 routers + schemas
- Celery async analysis pipeline (whisper → hubert → spacy → speechbrain → scoring engine)
- Scoring formula v2 with adaptive decisions
- WebSocket real-time score delivery via Redis pub/sub
- Plan generator service
- Patient frontend: home, tasks, exercise recorder, score display, progress
- Therapist frontend: dashboard, patient management, plan Kanban editor
- Security fixes from code review (input validation, auth guards, WS timeout)

### In Progress / Recent Changes
- **DB schema v2.0 redesign** — all ORM models rewritten from scratch; database reset to empty
  - `content.py` — merged `speech_target`, `evaluation_target`, `feedback_rule`, `prompt_scoring` into a single `prompt` table; added `AdaptiveThreshold`, `DefectPAThreshold`, `EmotionWeightsConfig` models
  - `baseline.py` — added `BaselineDefectMapping` many-to-many bridge
  - `plan.py` — added `PlanRevisionHistory` for Kanban audit log; `start_date`/`end_date` now `Date` type
  - `operations.py` — new file with `AudioFile` (upload tracking/cleanup) and `TherapistNotification` models
  - `users.py` — `patient.date_of_birth` now `Date` type; streak tracking columns added
  - `__init__.py` — updated to export all new model classes
  - `reset_db.py` — helper script to drop + recreate all tables cleanly
- `whisper_asr.py` — improved ASR with language hints and fallback handling
- `analysis.py` — hardened Celery task with proper error isolation per ML step
- `ws.ts` — added connection timeout and cleanup
- `Recorder.tsx` — mic permission flow + cleanup
- `tasks/[assignmentId]/page.tsx` — score display integration

### Pending / Backlog
- Baseline assessment frontend (patient flow)
- E2E tests (no tests exist yet — 0% coverage)
- Unit tests for scoring engine and ML modules
- Production deployment config (Docker, env management)
- Rate limiting on API endpoints
- CSRF protection
- Audio file cleanup (uploads directory grows unbounded)

---

## Known Issues / Constraints

- **Windows Celery:** Must use `-P solo` pool; `prefork` not supported on Windows
- **ML model cold start:** First Celery task loads ~1–2GB of models; subsequent tasks fast due to singleton `@lru_cache`
- **No audio cleanup:** `uploads/` directory is never purged — needs cron or post-processing cleanup
- **Sync DB driver:** Celery tasks use `psycopg2` (sync) because Celery workers can't use asyncpg; two separate `DATABASE_URL` vars required
- **spaCy fallback:** If `en_core_web_lg` is not installed, falls back to blank tokenizer — disfluency detection degrades silently
- **HuBERT fallback:** Returns hardcoded 70% phoneme accuracy on any model error — masks real failures
- **No test coverage:** Zero automated tests exist — all testing is manual
- **Token storage:** JWT stored in localStorage (XSS risk in high-security contexts)
- **WebSocket auth:** Token sent as first message payload (not HTTP header) — acceptable for this use case

---

## Future Improvements

- Docker Compose for full stack (API + worker + Redis + DB)
- Add pytest suite for scoring engine (pure functions, easy to test)
- Periodic audio file cleanup task in Celery beat
- Rate limiting via `slowapi` on all endpoints
- Baseline assessment frontend completion
- Dashboard analytics (therapist view of aggregate patient metrics)
- Push notifications (instead of/alongside WebSocket) for async results
- Multi-language support in ASR (Whisper supports 99 languages)
- Session replay — store timestamped attempt audio for therapist review
- Export progress reports (PDF) for clinical records

---

## Notes for AI Assistants

### Assumptions
- Database is empty (fresh schema v2.0, reset on 2026-04-05) — seed data must be inserted before testing; do NOT assume data exists
- Audio files are stored at `server/uploads/` (relative to server root, set by `UPLOAD_DIR` env var)
- All ML models run locally on the Celery worker process, not on the FastAPI process
- The Celery task (`analyze_attempt`) is the only place ML inference happens
- `DATABASE_URL` (asyncpg) = FastAPI only; `DATABASE_URL_SYNC` (psycopg2) = Celery only

### Coding Patterns to Follow
- **FastAPI:** All route handlers are `async def`; use `AsyncSession` from `get_db` dependency
- **Celery tasks:** Use `db = SessionLocal()` (sync) and close in `finally` block
- **Error handling:** Raise `HTTPException` with explicit status codes; never swallow exceptions silently
- **Auth:** Use `require_therapist()` or `require_patient()` as FastAPI dependencies (not inline JWT decode)
- **Schemas:** Pydantic v2 style (`model_config = ConfigDict(from_attributes=True)`)
- **Frontend API calls:** Use `lib/api.ts` helpers (`get<T>`, `post<T>`, `upload<T>`), never raw fetch
- **State:** Auth state lives in `store/auth.ts` (Zustand); read with `useAuthStore()`
- **Immutability:** Create new objects rather than mutating — especially in React state
- **File size:** Keep files under 800 lines; split by concern if growing large

### Things to Avoid
- Do NOT add `asyncpg` imports or `async` database calls inside Celery tasks
- Do NOT call ML models directly from FastAPI route handlers (always via Celery)
- Do NOT hardcode secrets, credentials, or environment-specific URLs
- Do NOT add `console.log` / `print` debug statements in committed code
- Do NOT run Alembic migrations unless explicitly requested — use `reset_db.py` to drop/recreate tables during dev; schema is managed via SQLAlchemy `create_all`
- Do NOT add `@lru_cache` to functions that take mutable arguments or database sessions
- Do NOT bypass WebSocket auth (the 10-second timeout + role check is intentional security)
- Do NOT use `git add .` — stage specific files to avoid committing `.env` or `uploads/`
