# SpeechPath — Full Build Design Spec
**Date:** 2026-04-04  
**Status:** Approved

---

## 1. What We're Building

SpeechPath is a full-stack speech therapy platform with two roles — therapist and patient. Therapists manage patients, generate weekly therapy plans, and track progress. Patients complete speech exercises, get real-time AI scoring, and view their progress.

This is a fresh build from zero using an existing Neon PostgreSQL database (fully migrated, fully seeded with content).

---

## 2. Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS v4 |
| State | Zustand 5.x with persist middleware |
| Drag & Drop | @dnd-kit/core, @dnd-kit/sortable |
| Charts | Recharts 3.x |
| Backend | FastAPI 0.115.x, Uvicorn, Pydantic v2 |
| ORM | SQLAlchemy 2.0 async (asyncpg) for API routes |
| DB | Neon PostgreSQL (existing schema + seed data, no migrations needed) |
| Sync DB | psycopg2-binary for Celery workers |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| Task queue | Celery 5.4.x |
| Broker | Redis (local) |
| Real-time | Redis pub/sub + FastAPI WebSocket relay |
| ASR | OpenAI Whisper (whisper-small model) |
| Phoneme | torchaudio HuBERT + forced_align |
| NLP | spaCy en_core_web_lg |
| Emotion | SpeechBrain IEMOCAP classifier |

---

## 3. Repository Structure

```
sppech-therapy-final/
├── client/
│   ├── app/
│   │   ├── (auth)/              # login, register pages (no layout chrome)
│   │   ├── therapist/           # therapist role layout + pages
│   │   │   ├── layout.tsx
│   │   │   ├── dashboard/
│   │   │   ├── patients/
│   │   │   │   ├── page.tsx     # patient list
│   │   │   │   └── [id]/        # patient detail (baseline, plan, progress)
│   │   │   ├── plans/[planId]/  # Kanban plan editor
│   │   │   └── profile/
│   │   └── patient/             # patient role layout + pages
│   │       ├── layout.tsx
│   │       ├── home/
│   │       ├── baseline/
│   │       ├── tasks/
│   │       │   └── [assignmentId]/  # exercise page
│   │       ├── progress/
│   │       └── profile/
│   ├── components/
│   │   ├── ui/                  # NeoButton, NeoCard, NeoInput, NeoSelect, skeletons
│   │   ├── therapist/           # TherapistNav, PatientCard, KanbanBoard, etc.
│   │   └── patient/             # PatientNav, TaskCard, Recorder, ScoreDisplay, etc.
│   ├── lib/
│   │   ├── api.ts               # fetch wrapper with 15s/60s timeouts
│   │   └── ws.ts                # WebSocket client with polling fallback
│   ├── store/
│   │   └── auth.ts              # Zustand auth store (role, token, userId, hydrated)
│   └── types/                   # shared TypeScript types
│
├── server/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, router mounts, WS endpoint
│   │   ├── config.py            # pydantic-settings from .env
│   │   ├── database.py          # async engine + get_db dependency
│   │   ├── auth.py              # JWT creation, require_therapist, require_patient
│   │   ├── models/              # SQLAlchemy ORM models (one file per domain)
│   │   │   ├── users.py
│   │   │   ├── content.py
│   │   │   ├── baseline.py
│   │   │   ├── plan.py
│   │   │   └── scoring.py
│   │   ├── schemas/             # Pydantic v2 request/response schemas
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── therapist.py
│   │   │   ├── plans.py
│   │   │   ├── patient.py
│   │   │   ├── baseline.py
│   │   │   ├── session.py
│   │   │   └── progress.py
│   │   ├── services/            # business logic (plan generation, adaptive engine)
│   │   ├── tasks/
│   │   │   └── analysis.py      # Celery task: analyze_attempt()
│   │   ├── ml/
│   │   │   ├── whisper_asr.py
│   │   │   ├── hubert_phoneme.py
│   │   │   ├── spacy_disfluency.py
│   │   │   └── speechbrain_emotion.py
│   │   └── scoring/
│   │       └── engine.py        # formula v2 scoring + adaptive decision
│   ├── .env
│   └── requirements.txt
│
├── client/.env.local
└── docs/
```

---

## 4. Database

The Neon PostgreSQL database is fully set up — 27 tables, all migrations applied, all content seeded. No migration or seeding work needed.

**Seed data available:**
- 33 defects (articulation, fluency, cognition categories)
- 30 tasks across 3 difficulty levels (90 task_level rows)
- 180 prompts with full satellite records (speech_target, evaluation_target, feedback_rule, prompt_scoring)
- 90 adaptive_threshold rows
- 30 task_scoring_weights rows
- Emotion weights config for child + adult age groups

**Connection:**
- FastAPI (async): `postgresql+asyncpg://...` via DATABASE_URL
- Celery (sync): `postgresql://...` via DATABASE_URL_SYNC

---

## 5. Authentication & Authorization

- Both roles register and login via `/auth` endpoints
- JWT issued immediately on registration (patient starts as `status=pending`)
- Patient endpoints blocked by `require_patient` until therapist approves (`status=approved`)
- Therapist endpoints blocked by `require_therapist`
- Frontend: Zustand auth store persists `token`, `role`, `userId`, `fullName`, `hydrated`
- Role-guarded layouts redirect unauthenticated users to login

**Therapist registration fields:** name, email, password, years of experience  
**Patient registration fields:** name, age/DOB, email, gender, therapist code, password

---

## 6. Build Phases

### Phase 1 — Scaffold + Auth
**Backend:** FastAPI app wired to Neon, config/database/auth modules, `POST /auth/register/therapist`, `POST /auth/register/patient`, `POST /auth/login`, `GET /auth/me`, `GET /health`  
**Frontend:** Next.js project, Tailwind v4 + neo-brutal tokens (Space Grotesk, `#FFFDF5` bg, `#FF6B6B` accent, `#FFD93D` secondary), NeoButton/NeoCard/NeoInput/NeoSelect components, auth store, therapist + patient login/register pages, role-guarded layouts

### Phase 2 — Therapist Patient Management
**Backend:** `GET /therapist/dashboard`, `GET /therapist/patients`, `GET /therapist/patients/{id}`, `POST /therapist/patients/{id}/approve`, `POST /therapist/patients/{id}/reject`, `GET /therapist/profile`, `GET /therapist/defects`  
**Frontend:** Therapist layout (red nav), dashboard page (patient count, pending approvals), patient list with card view, patient detail page (approve/reject actions), profile page with therapist_code display

### Phase 3 — Baseline Assessment
**Backend:** `GET /baseline/exercises` (filter by patient defects), `POST /baseline/submit` (store aggregated scores, compute level: 50–70=easy, 70–80=medium, >80=advanced), `GET /baseline/result`, `GET /therapist/patients/{id}/baseline`  
**Frontend:** Patient baseline page — fetches exercises by defect, TTS plays instruction, mic records response, uploads audio per item, displays per-item score results; on completion submits aggregated scores to `/baseline/submit`; therapist sees baseline scores per patient

### Phase 4 — Plan Generation + Kanban
**Backend:** `POST /plans/generate` (draft plan from defect + level), `GET /plans/{id}`, `POST /plans/{id}/tasks`, `PATCH /plans/{id}/tasks/{assignment_id}` (day_index drag/drop), `DELETE /plans/{id}/tasks/{assignment_id}`, `POST /plans/{id}/approve`, `GET /plans/{id}/tasks-for-defects` (dropdown options)  
**Frontend:** Kanban board (dnd-kit, 7 day columns), add/update/delete task cards, task name dropdown filtered by defect, approve plan button; patient task page shows only today's approved tasks

### Phase 5 — Exercise + ML Pipeline
**Backend:** `POST /session/start`, `POST /session/{id}/attempt` (multipart audio upload → Celery task), `GET /session/attempt/{id}` (polling), `GET /session/{id}`, WebSocket `/ws/{patient_id}`  
**Celery worker:** `analyze_attempt()` → Whisper-small ASR → HuBERT phoneme alignment → spaCy disfluency → SpeechBrain emotion → formula v2 scoring engine → persist `attempt_score_detail` → publish `score_ready` to Redis → WebSocket delivers to browser  
**Frontend:** Exercise page — TTS instruction plays first (mic disabled), then mic activates, records audio, uploads, shows pending state, receives score via WebSocket (polling fallback), displays transcript + all accuracy metrics + final score

### Phase 6 — Progress Dashboards
**Backend:** `GET /patient/progress`, `GET /therapist/patients/{id}/progress` — aggregate last 8 weeks: weekly trend, per-task metrics, emotion distribution, recent attempts, summary counters  
**Frontend:** Patient progress page (Recharts line/bar charts, accuracy level, positive feedback); therapist patient progress view (same data, clinical framing)

---

## 7. ML Pipeline Detail

```
Audio upload (multipart)
    │
POST /session/{id}/attempt  →  FastAPI stores file + creates session_prompt_attempt (result=pending)
    │                           dispatches Celery task
    │
analyze_attempt(attempt_id) [Celery worker, psycopg2]:
    ├── Load attempt + prompt + scoring config from DB
    ├── Whisper-small: transcript, token confidence, timestamps
    ├── HuBERT forced_align: phoneme-level alignment
    ├── spaCy: disfluency rate, pause score
    ├── SpeechBrain IEMOCAP: dominant_emotion, emotion_score
    ├── scoring/engine.py: formula v2
    │     speech_score = PA×w_pa + WA×w_wa + FS×w_fs + SRS×w_srs + CS×w_cs
    │     engagement = emotion×w_emotion + behavioral×w_behavioral
    │     final = speech×fusion_w_speech + engagement×fusion_w_engagement
    │     post-fusion rules (PA cap, engagement penalty/boost)
    │     adaptive decision: advance / stay / drop
    ├── Write attempt_score_detail
    ├── Update patient_task_progress (consecutive passes/fails, overall_accuracy)
    └── Publish score_ready → Redis ws:patient:{id} → FastAPI WS → browser
```

Scoring weights are per-task from `task_scoring_weights` table; fallback to hardcoded defaults if no row exists.

---

## 8. Real-time Score Delivery

- Client opens `ws://localhost:8000/ws/{patient_id}` on exercise page load
- Server sends `{"type": "ping"}` keepalive every 30s
- On score ready: `{"type": "score_ready", "attempt_id": "...", "final_score": ..., "pass_fail": "...", "adaptive_decision": "...", ...}`
- Client fallback: if WS disconnected, polls `GET /session/attempt/{id}` every 3s until result != "pending"

---

## 9. Design System

- **Font:** Space Grotesk
- **Background:** `#FFFDF5`
- **Therapist accent:** `#FF6B6B` (red nav)
- **Patient accent:** `#FFD93D` (yellow nav)
- **Muted:** `#C4B5FD`
- **Borders:** `border-4 border-black`
- **Shadows:** `shadow-[4px_4px_0px_0px_#000]`
- **Buttons:** press = shadow collapse + 2px shift
- **Components:** NeoButton (primary/secondary/ghost, sm/md/lg), NeoCard (default/muted/accent/secondary), NeoInput, NeoSelect, SkeletonPage, SkeletonList, SkeletonCard, ErrorBanner

---

## 10. API Contract Summary

35 endpoints total across 7 routers. Full detail in `docs/api-design.md`. Client wraps all HTTP in `client/lib/api.ts` with 15s JSON timeout and 60s upload timeout.

---

## 11. Environment

**server/.env** — DATABASE_URL (asyncpg), DATABASE_URL_SYNC (psycopg2), REDIS_URL, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, UPLOAD_DIR, DEBUG  
**client/.env.local** — NEXT_PUBLIC_API_URL, NEXT_PUBLIC_WS_URL

---

## 12. Out of Scope

- Automated test suite (no tests configured in this build)
- Containerization (dev runs as separate processes)
- Production deployment config
- Weekly report generation (post-MVP)
