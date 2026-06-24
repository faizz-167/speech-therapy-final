# SpeechPath — Project Documentation

**SpeechPath** is a full-stack speech therapy platform. Therapists design and monitor personalized treatment plans; patients practice exercises with real-time ML-based scoring, emotion tracking, and adaptive difficulty.

---

## Documentation Index

| File | Contents |
|------|----------|
| [architecture.md](./architecture.md) | System design, tech stack, component map |
| [database-design.md](./database-design.md) | All tables, columns, relationships, ERD |
| [backend-flow.md](./backend-flow.md) | API endpoints, business logic, workflows |
| [ml-pipeline.md](./ml-pipeline.md) | ML models, scoring math, adaptive engine |
| [frontend.md](./frontend.md) | Page structure, state management, components |
| [setup.md](./setup.md) | Local dev setup, environment variables |

---

## Quick Summary

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI + Uvicorn (async) |
| Database | PostgreSQL (Neon) via SQLAlchemy 2.0 async |
| Job Queue | Celery + Redis |
| Auth | JWT (python-jose) + bcrypt |
| ML | Whisper, HuBERT, SpeechBrain, spaCy |
| Frontend | Next.js 14 (App Router) + React 19 |
| State | Zustand + TanStack React Query |
| Styling | Tailwind CSS 4 |
| Real-time | WebSocket + Redis pub/sub |

---

## Core User Roles

**Therapist**
- Registers independently; gets a unique `therapist_code`
- Approves patients, assigns defect categories
- Creates/approves therapy plans
- Reviews AI-flagged attempts and escalation alerts

**Patient**
- Registers with a `therapist_code`; waits for approval
- Completes a one-time baseline assessment
- Receives a weekly 7-day therapy plan
- Does daily exercise sessions; gets real-time feedback scores
