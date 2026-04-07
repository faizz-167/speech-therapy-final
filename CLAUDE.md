# CLAUDE.md

Repo guidance for AI coding assistants working in this project.

## Project Summary

SpeechPath is a split-stack speech-therapy platform with a Next.js 16 client and a FastAPI backend. Therapists register, approve patients via therapist codes, assign defects, run baseline assessments, generate weekly therapy plans, and review patient progress. Patients complete baseline and therapy exercises by recording audio, while Celery workers score attempts with ASR, phoneme, fluency, and emotion models and stream results back over WebSockets.

## Tech Stack

- Client: Next.js 16 App Router + React 19 + TypeScript
- Styling: Tailwind CSS v4 + custom neo-brutalist utility components
- State: Zustand persisted auth store
- Backend: FastAPI + Pydantic v2 + SQLAlchemy 2 async ORM
- Database: Postgres with asyncpg for app traffic and psycopg2 for worker/reset scripts
- Auth: custom JWT bearer auth with bcrypt password hashing
- Queue/runtime: Celery + Redis
- ML/audio: OpenAI Whisper, torchaudio MMS forced alignment, SpeechBrain emotion model, spaCy disfluency heuristics

## Source Of Truth

- Backend app entry: `server/app/main.py`
- Settings/env parsing: `server/app/config.py`
- DB base/session: `server/app/database.py`
- Auth helpers and role guards: `server/app/auth.py`
- ORM schema: `server/app/models/*`
- API contracts: `server/app/schemas/*`
- Therapist APIs: `server/app/routers/therapist.py`
- Patient APIs: `server/app/routers/patient.py`
- Baseline flow: `server/app/routers/baseline.py`
- Therapy session flow: `server/app/routers/session.py`
- Plan generation and plan APIs: `server/app/services/plan_generator.py`, `server/app/routers/plans.py`
- Progress aggregation: `server/app/routers/progress.py`
- Therapy scoring pipeline: `server/app/tasks/analysis.py`
- Baseline scoring pipeline: `server/app/tasks/baseline_analysis.py`
- Scoring formula defaults: `server/app/scoring/engine.py`
- ML wrappers: `server/app/ml/*`
- Seed content and schema reset: `server/seed_data.py`, `server/reset_db.py`
- Client API and WS clients: `client/lib/api.ts`, `client/lib/ws.ts`
- Client auth state: `client/store/auth.ts`
- Global UI shell: `client/app/layout.tsx`, `client/app/globals.css`

## Architecture Rules

1. Keep API route handlers thin; shared business logic belongs in `server/app/services`, `server/app/tasks`, `server/app/auth`, or model-adjacent helpers.
2. Do not bypass the ORM schema. If you change tables, keep `server/app/models/*`, `server/reset_db.py`, and `server/seed_data.py` aligned.
3. Keep async app traffic on SQLAlchemy/asyncpg and worker-style scoring jobs on the existing psycopg2 path unless the whole execution model is being changed deliberately.
4. Preserve role checks. Therapist routes depend on `require_therapist`, patient routes depend on `require_patient`, and patient access is blocked until approval.
5. Preserve the WebSocket auth handshake on `/ws/{patient_id}`. The first client message must carry the JWT token.
6. Keep the current storage model for audio attempts: files are written to `settings.upload_dir`, and DB rows store file paths plus metadata.
7. Keep the client/server contract synchronized. If request fields or response shapes change, update the matching client code in `client/lib/*`, pages, and components.

## Current Product Constraints

- The app has exactly two user roles: `therapist` and `patient`.
- Patient signup requires a valid therapist code.
- Newly registered patients start as `pending` and cannot use protected patient flows until approved.
- Therapist approval stores assigned defect IDs in `patient.pre_assigned_defect_ids`.
- Baseline exercise fetches are capped to 7 non-clinician-rated items per session.
- Baseline sessions and therapy sessions are separate `session.session_type` values: `baseline` and `therapy`.
- Therapy sessions must be linked to either an approved `assignment_id` or an approved `plan_id`.
- Current plan generation creates a 7-day draft plan with up to 14 task slots.
- Patient task lists are day-based using `date.today().weekday()`.
- Audio files are currently saved locally under `upload_dir`; they are not stored in Postgres blobs.

## Authentication And Routing

- Backend auth is stateless JWT bearer auth from `server/app/auth.py`.
- Tokens include `sub` and `role`, and expiry defaults to 10080 minutes.
- Therapist-only APIs are under `/therapist/*`.
- Patient-only APIs are under `/patient/*`, `/baseline/*`, and `/session/*`.
- Client route protection is currently layout-based in `client/app/therapist/layout.tsx` and `client/app/patient/layout.tsx`.
- Client auth persistence lives in localStorage via the `auth-storage` Zustand key.
- The login page redirects users by role to `/therapist/dashboard` or `/patient/home`.

## Realtime And Queueing

- FastAPI publishes score-ready events over Redis pub/sub channels named `ws:patient:{patient_id}`.
- The WebSocket endpoint sends a `ping` every 30 seconds and forwards `score_ready` payloads to the patient client.
- Therapy scoring runs in `app.tasks.analysis.analyze_attempt`.
- Baseline scoring runs in `app.tasks.baseline_analysis.analyze_baseline_attempt`.
- Celery uses Redis for both broker and backend.
- On Windows, Celery is intentionally configured to use the `solo` worker pool.

## Scoring Behavior

`server/app/tasks/analysis.py` currently does this:

1. Loads the attempt, prompt, task, patient, therapist, and scoring config from Postgres.
2. Resolves task-level scoring weights, task WPM targets, defect PA thresholds, and prompt-level adaptive overrides.
3. Transcribes audio with Whisper using a sanitized expected-text hint when available.
4. Treats empty or near-empty low-confidence audio as no speech and stores a failed attempt plus therapist review notification.
5. Computes word accuracy, phoneme accuracy, fluency/disfluency, speech-rate score, response-latency score, task-completion score, answer-quality score, and emotion-derived engagement.
6. Applies the formula from `server/app/scoring/engine.py` to produce speech, behavioral, engagement, and final scores.
7. Enforces stricter fail behavior when assigned defect PA thresholds are not met.
8. Updates `attempt_score_detail`, `session_prompt_attempt`, `patient_task_progress`, and `session_emotion_summary`, then publishes a WebSocket event.

Do not change scoring thresholds casually. They drive adaptive progression, therapist review flags, and progress reporting.

## Baseline Flow

`server/app/routers/baseline.py` currently does this:

1. Loads baseline assessments mapped to the patient’s assigned defects.
2. Excludes `clinician_rated` baseline items from the self-serve patient flow.
3. Creates a dedicated baseline session before any item attempts are uploaded.
4. Saves each baseline recording locally and queues ML scoring asynchronously.
5. Aggregates scored attempts into `patient_baseline_result` and `baseline_item_result` rows on completion.
6. Maps baseline scores into `easy`, `medium`, or `advanced` severity bands.

## Therapy Plan Behavior

- Weekly plan generation is defect-driven via `task_defect_mapping`.
- Plan difficulty is chosen from the passed `baseline_level`, with fallback to `easy` if no tasks exist at that level.
- New plans start as `draft` and must be explicitly approved before patients can use them.
- Plan edits are audit-trailed in `plan_revision_history`.
- Patient prompt selection prefers `patient_task_progress.current_level_id`, then falls back to the latest baseline severity.

## Database And Seed Notes

- ORM models are registered through `import app.models` in `server/reset_db.py`.
- `reset_db.py` drops and recreates the entire `public` schema and is destructive by design.
- `seed_data.py` is the canonical seed source for defects, thresholds, tasks, prompts, scoring weights, and baseline content.
- The seed set is large and clinically coupled; do not hand-edit seeded IDs casually without tracing every mapping.

## UI Notes

- The current client visual language is neo-brutalist, not a minimal SaaS style.
- Global font is Space Grotesk from `@fontsource/space-grotesk`.
- Core palette tokens live in `client/app/globals.css`: `neo-bg`, `neo-accent`, `neo-secondary`, `neo-muted`, and `neo-black`.
- Reusable UI primitives live in `client/components/ui/*` and should be preferred over ad hoc button/input/card styling.
- Keep the grid-pattern background and heavy black borders/shadows unless the task explicitly rebrands the app.

## Environment Variables

Backend settings currently require or use:

- `DATABASE_URL`
- `DATABASE_URL_SYNC`
- `REDIS_URL`
- `SECRET_KEY`
- `ALGORITHM`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `UPLOAD_DIR`
- `DEBUG`
- `CORS_ORIGINS`

Client runtime config currently uses:

- `NEXT_PUBLIC_API_URL`
- `NEXT_PUBLIC_WS_URL`

## Working Rules For Assistants

1. Verify claims against code before documenting them.
2. Do not make changes until you have 95% confidence in what needs to be built; ask follow-up questions until you reach that confidence.
3. Prefer editing shared backend logic in `server/app/*` over duplicating behavior in route handlers.
4. Keep request and response contracts backward-compatible unless the task explicitly requires a breaking change.
5. When changing auth, update both backend bearer handling and the client Zustand/localStorage flow.
6. When changing scoring or adaptive behavior, trace impacts across `analysis.py`, `baseline_analysis.py`, `engine.py`, progress APIs, and patient UI.
7. If architecture or product behavior changes, update this file in the same task.