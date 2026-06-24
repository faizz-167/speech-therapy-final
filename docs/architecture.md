# Architecture

## System Overview

```
┌────────────────────────────────────────────────────────┐
│                    CLIENT (Browser)                    │
│         Next.js 14 App Router · React 19               │
│         Zustand · TanStack Query · Tailwind 4          │
└────────────────────┬────────────────────┬──────────────┘
                     │ HTTP/REST           │ WebSocket
                     ▼                    ▼
┌────────────────────────────────────────────────────────┐
│                  SERVER (FastAPI)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐ │
│  │  Routers │  │ Schemas  │  │      Auth (JWT)       │ │
│  │ auth     │  │ Pydantic │  │  password bcrypt      │ │
│  │ therapist│  │ request/ │  │  role-based deps      │ │
│  │ patient  │  │ response │  └──────────────────────┘ │
│  │ baseline │  └──────────┘                           │
│  │ plans    │                                         │
│  │ session  │  ┌──────────────────────────────────┐  │
│  │ progress │  │        Celery Workers            │  │
│  └──────────┘  │  analysis · baseline_analysis    │  │
│                │  attempt_persistence · session_  │  │
│                │  queue · plan_regeneration        │  │
│                └───────────┬──────────────────────┘  │
└────────────────────────────┼────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  PostgreSQL  │   │    Redis     │   │  ML Models   │
│  (Neon)      │   │  job queue   │   │  Whisper ASR │
│  SQLAlchemy  │   │  pub/sub     │   │  HuBERT      │
│  async ORM   │   │  WebSocket   │   │  SpeechBrain │
└──────────────┘   └──────────────┘   │  spaCy       │
                                      └──────────────┘
```

---

## Tech Stack

### Backend
| Component | Library | Version |
|-----------|---------|---------|
| Web framework | FastAPI | 0.115.5 |
| ASGI server | Uvicorn | latest |
| ORM | SQLAlchemy | 2.0.36 |
| Async DB driver | asyncpg | 0.30.0 |
| Sync DB driver (Celery) | psycopg2-binary | 2.9.10 |
| Job queue | Celery | 5.4.0 |
| Cache / pub-sub | Redis | 5.2.1 |
| Auth tokens | python-jose | latest |
| Password hashing | passlib + bcrypt | latest |
| Schema validation | Pydantic v2 | latest |
| DB migrations | Alembic | 1.14.0 |
| Speech-to-text | OpenAI Whisper | 20240930 |
| Deep learning | PyTorch + TorchAudio | 2.5.1 |
| Emotion recognition | SpeechBrain | 1.0.2 |
| Transformer models | HuggingFace transformers | 4.46.3 |
| Disfluency detection | spaCy | 3.8.3 |
| Audio I/O | Soundfile | 0.12.1 |
| Settings | pydantic-settings | latest |

### Frontend
| Component | Library | Version |
|-----------|---------|---------|
| Framework | Next.js | 16.2.2 |
| UI library | React | 19.2.4 |
| Global state | Zustand | 5.0.12 |
| Server state | TanStack React Query | 5.96.2 |
| Styling | Tailwind CSS | 4 |
| Drag-and-drop | @dnd-kit | latest |
| Charts | Recharts | 3.8.1 |
| Notifications | Sonner | latest |

---

## Directory Structure

```
sppech-therapy-final/
├── server/                        # FastAPI backend
│   ├── app/
│   │   ├── main.py               # App entry, router mounts, WebSocket
│   │   ├── auth.py               # JWT encode/decode, role deps
│   │   ├── config.py             # .env settings via pydantic-settings
│   │   ├── database.py           # Async engine, session factory, Base
│   │   ├── celery_app.py         # Celery config, Redis broker
│   │   ├── enums.py              # Shared enums (roles, statuses)
│   │   ├── constants.py          # Numeric/string constants
│   │   ├── models/               # SQLAlchemy ORM models
│   │   │   ├── users.py          # Therapist, Patient
│   │   │   ├── baseline.py       # Baseline assessments & attempts
│   │   │   ├── content.py        # Defects, Tasks, Levels, Prompts, Weights
│   │   │   ├── plan.py           # TherapyPlan, PlanTaskAssignment, RevisionHistory
│   │   │   ├── scoring.py        # Session, Attempt, ScoreDetail, Progress
│   │   │   └── operations.py     # AudioFile, Notifications
│   │   ├── routers/              # Route handlers (business logic lives here)
│   │   │   ├── auth.py
│   │   │   ├── therapist.py
│   │   │   ├── patient.py
│   │   │   ├── plans.py
│   │   │   ├── baseline.py
│   │   │   ├── session.py
│   │   │   └── progress.py
│   │   ├── schemas/              # Pydantic request & response models
│   │   │   ├── auth.py
│   │   │   ├── therapist.py
│   │   │   ├── patient.py
│   │   │   ├── plans.py
│   │   │   ├── baseline.py
│   │   │   ├── session.py
│   │   │   └── progress.py
│   │   ├── services/
│   │   │   └── plan_generator.py # Plan creation logic
│   │   ├── tasks/                # Celery async tasks
│   │   │   ├── analysis.py       # Therapy attempt ML pipeline
│   │   │   ├── baseline_analysis.py
│   │   │   ├── attempt_persistence.py
│   │   │   ├── session_queue.py  # Adaptive prompt queue
│   │   │   ├── scoring_helpers.py
│   │   │   └── plan_regeneration.py
│   │   ├── ml/                   # ML model wrappers
│   │   │   ├── whisper_asr.py
│   │   │   ├── hubert_phoneme.py
│   │   │   ├── speechbrain_emotion.py
│   │   │   └── spacy_disfluency.py
│   │   ├── scoring/
│   │   │   └── engine.py         # Final score computation
│   │   └── utils/
│   │       ├── feedback.py
│   │       ├── plan_lock.py
│   │       └── session_notes.py
│   ├── requirements.txt
│   ├── .env
│   ├── reset_db.py               # Dev: drop & recreate schema
│   └── seed_data.py              # Dev: load clinical seed data
│
├── client/                        # Next.js frontend
│   ├── app/                       # App Router pages
│   │   ├── layout.tsx
│   │   ├── page.tsx               # Landing
│   │   ├── login/
│   │   ├── register/
│   │   │   ├── therapist/
│   │   │   └── patient/
│   │   ├── patient/               # All patient pages
│   │   └── therapist/             # All therapist pages
│   ├── components/                # Shared React components
│   ├── hooks/                     # Custom React hooks
│   ├── lib/                       # API client, helpers
│   ├── store/                     # Zustand stores
│   ├── types/                     # TypeScript interfaces
│   └── public/                    # Static assets
│
├── docs/                          # This documentation
├── docker-compose.redis.yml       # Redis container
└── walkthrough.md                 # Quick setup guide
```

---

## Data Flow: Therapy Attempt (End-to-End)

```
Patient records audio
        │
        ▼
POST /session/{id}/attempt  ──▶  FastAPI router
        │                           │
        │  saves audio file          │  returns { attempt_id, status: "pending" }
        │                           │
        ▼                           ▼
Celery task: analysis.py       Client polls
        │                      GET /session/attempt/{attempt_id}
        ├─ Whisper ASR
        ├─ HuBERT phoneme alignment
        ├─ spaCy disfluency
        ├─ SpeechBrain emotion
        ├─ Scoring engine (weighted fusion)
        ├─ Adaptive decision (advance / stay / drop)
        └─ Write attempt_score_detail to DB
                │
                ▼
        attempt_persistence.py
                │
                ├─ Update patient_task_progress
                ├─ Check escalation trigger
                ├─ Publish to Redis pub/sub
                │
                ▼
        WebSocket delivers score to client instantly
```

---

## Real-Time Architecture

```
FastAPI WebSocket endpoint: /ws/{patient_id}
        │
        │  subscribes to Redis channel: patient:{patient_id}
        │
Celery task (after scoring)
        │
        └─ redis.publish("patient:{id}", score_payload_json)
                │
                ▼
        WebSocket pushes to connected browser
```

---

## Authentication Flow

```
POST /auth/login
        │
        ├─ Verify email exists
        ├─ bcrypt verify password
        ├─ Check patient status = "approved" (patients only)
        ├─ Create JWT: { sub: user_id, role: "therapist"|"patient" }
        └─ Return token + user info

Protected routes use FastAPI dependency injection:
  get_current_therapist()  ──▶  decode JWT, verify role = therapist
  get_current_patient()    ──▶  decode JWT, verify role = patient
```
