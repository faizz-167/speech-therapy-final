# Frontend Alignment Audit And Change Plan

## Goal

Bring the current Next.js frontend into full alignment with the current FastAPI backend and turn it from a functional prototype into a production-ready application.

This document is based on the current codebase as of 2026-04-07:

- Frontend: `client/app`, `client/components`, `client/lib`, `client/store`
- Backend: `server/app/routers`, `server/app/schemas`, `server/app/tasks`, `server/app/models`

---

## Executive Summary

The frontend is partially aligned, but it still reflects an earlier backend shape and earlier product assumptions.

What is already working:

- Auth flows are connected and usable.
- Patient baseline now uses the ML upload/poll/complete flow.
- Patient therapy sessions use the current `/session` upload + scoring pipeline.
- Therapist plan generation and assignment editing are connected to the live backend.
- Progress pages use the current progress API.

What is still prototype-level or misaligned:

- Frontend contracts are duplicated manually and will drift from backend schemas.
- Several screens render hardcoded or placeholder data instead of backend data.
- The frontend does not expose important v2 backend capabilities:
  - `therapist_notification`
  - `plan_revision_history`
  - richer adaptive progression state
  - deeper baseline review details
- State management, API handling, auth bootstrapping, and error handling are still thin for production.
- Navigation and page behavior still use imperative `window.location.href`, `alert`, and `confirm` in several places.

Bottom line:

- The app is a usable internal prototype.
- It is not yet a production-ready frontend for the current backend.

---

## Current Frontend State

## 1. Architecture

Current frontend architecture:

- Next.js App Router
- Mostly client components with `useEffect` data fetching
- Zustand persisted auth store
- Thin `api.ts` wrapper around `fetch`
- Manual TypeScript interfaces in `client/types/index.ts` and local page files
- No React Query/SWR cache layer
- No generated API client from OpenAPI/Pydantic schemas
- No centralized server-state loading/error/retry strategy

Strengths:

- Simple and easy to reason about
- Fast to iterate
- Good enough for initial flow validation

Weaknesses:

- Contract drift risk is high
- Repeated page-level loading/error logic
- No optimistic consistency rules
- No shared domain model for auth, plans, sessions, baseline, progress
- Weak production resilience around retries, reconnects, session expiry, and partial failures

---

## 2. Route And Feature Coverage

### Auth

Frontend coverage:

- `/login`
- `/register/therapist`
- `/register/patient`
- local auth persistence via Zustand

Backend coverage:

- `POST /auth/register/therapist`
- `POST /auth/register/patient`
- `POST /auth/login`
- `GET /auth/me`

Current state:

- Login and therapist registration are integrated.
- Patient registration ignores the token returned by the backend and instead shows a pending-approval message, which is acceptable from a product standpoint.
- `GET /auth/me` is not used anywhere, so the frontend never re-validates stored auth state after hydration.

Needed changes:

- Use `/auth/me` during app bootstrap to validate persisted auth.
- Add a centralized 401/403 handler that clears invalid auth and redirects safely.
- Replace manual role assumptions in layouts with a real auth bootstrap state.
- Add logout confirmation and session-expiry UX.

### Patient Area

Frontend coverage:

- `/patient/home`
- `/patient/tasks`
- `/patient/tasks/[assignmentId]`
- `/patient/baseline`
- `/patient/progress`
- `/patient/profile`

Backend coverage:

- `/patient/home`
- `/patient/tasks`
- `/patient/tasks/{assignment_id}/prompts`
- `/patient/tasks/{assignment_id}/complete`
- `/baseline/*`
- `/session/*`
- `/patient/progress`
- `/patient/profile`

Current state:

- The patient task flow works against the current backend.
- Baseline now matches the new ML flow.
- Progress is connected.
- Profile is only partially real.

### Therapist Area

Frontend coverage:

- `/therapist/dashboard`
- `/therapist/patients`
- `/therapist/patients/[id]`
- `/therapist/patients/[id]/baseline`
- `/therapist/patients/[id]/plan`
- `/therapist/patients/[id]/progress`
- `/therapist/profile`

Backend coverage:

- `/therapist/dashboard`
- `/therapist/patients`
- `/therapist/patients/{id}`
- `/therapist/patients/{id}/approve`
- `/therapist/patients/{id}/reject`
- `/therapist/defects`
- `/baseline/therapist-view/{patient_id}`
- `/plans/*`
- `/therapist/patients/{patient_id}/progress`

Current state:

- Therapist can approve patients, view baseline, generate plan, approve plan, add/delete/move tasks, and view progress.
- But the therapist UI still exposes only a subset of the backend’s real operational model.

---

## Frontend/Backend Misalignment By Area

## 3. Auth And App Shell

### Current frontend behavior

- Route protection is handled only by persisted local state in:
  - `client/app/patient/layout.tsx`
  - `client/app/therapist/layout.tsx`
- The frontend never calls `/auth/me`.
- Auth data is trusted until manually cleared.

### Why this is misaligned

- The backend already exposes `/auth/me`, but the frontend ignores it.
- If a token expires, is revoked, or becomes invalid, the UI will still treat the session as valid until an API call fails.
- There is no standard recovery path for unauthorized responses.

### Required changes

- Add an app bootstrap auth provider:
  - read persisted token
  - call `/auth/me`
  - populate canonical user state
  - redirect only after bootstrap resolves
- Add centralized API error handling for:
  - `401 Unauthorized`
  - `403 Forbidden`
  - network timeout
  - backend validation errors
- Move auth shape out of ad hoc local interfaces into a shared domain contract.

---

## 4. API Contract Management

### Current frontend behavior

- Interfaces are duplicated manually in:
  - `client/types/index.ts`
  - page-local interfaces across `client/app/**`
- The frontend is not generated from backend schemas or OpenAPI.

### Why this is misaligned

- The backend already defines canonical schemas in `server/app/schemas`.
- The frontend is at permanent risk of silently drifting.
- Several responses are only partially modeled in the frontend.

### Required changes

- Make the backend OpenAPI schema the source of truth.
- Generate a typed client for frontend consumption.
- Replace page-local interfaces with domain modules:
  - `auth`
  - `patient`
  - `baseline`
  - `session`
  - `plans`
  - `progress`
  - `therapist`
- Standardize API response typing and error envelopes.

Preferred production approach:

- Generate TS types from OpenAPI.
- Wrap them in feature-specific query/mutation hooks.

---

## 5. Patient Home

### Current frontend behavior

File:

- `client/app/patient/home/page.tsx`

What it does now:

- shows baseline-needed state
- shows pending-plan state
- shows approved-plan summary with today task count

Alignment status:

- Mostly aligned with `/patient/home`
- Good enough functionally

Gaps:

- No notifications surface
- No “resume today’s first task” action
- No recent baseline result summary
- No adaptive progression summary
- No session continuity state

Required changes:

- Add backend-aligned summary cards:
  - latest baseline level
  - approved plan status
  - today task count
  - current streak
  - latest dominant emotion / engagement trend if product wants it
- Add CTA priority logic:
  - baseline incomplete -> baseline CTA
  - baseline complete and no approved plan -> waiting state
  - approved plan and remaining tasks -> resume task CTA

Optional backend addition:

- a richer `/patient/home` payload so the page does not have to compose multiple APIs later.

---

## 6. Patient Profile

### Current frontend behavior

File:

- `client/app/patient/profile/page.tsx`

What is good:

- Reads `/patient/profile`
- Displays assigned defects

What is wrong:

- Therapist name is hardcoded as `Faiz`
- Diagnosis is hardcoded to `—`
- Member since is hardcoded to `01/04/2026`
- Best streak duplicates current streak instead of using a real backend field

Why this is misaligned:

- The page visually implies backend-backed profile data that the backend does not currently return.

Required changes:

Frontend-only:

- Remove hardcoded fields immediately or label them as unavailable.

Frontend + backend extension:

- Extend `/patient/profile` to include:
  - therapist name
  - primary diagnosis
  - created_at/member since
  - best streak
  - clinical notes summary if desired

Production-ready target:

- Patient profile must render only real backend data.
- No invented values in the UI.

---

## 7. Patient Tasks List

### Current frontend behavior

File:

- `client/app/patient/tasks/page.tsx`

Current state:

- Fetches `/patient/tasks`
- Uses `/patient/home` for plan summary fallback
- Displays only today’s tasks

What is missing:

- No grouping by plan/day
- No paused/in-progress distinction
- No task difficulty/level preview
- No task completion history

Alignment considerations:

- This page is aligned with the current backend endpoint, but the UX is still minimal.
- The backend model now has adaptive progression, task levels, and plan structure that the frontend does not surface.

Required changes:

- Improve task cards to show:
  - task mode
  - completion status
  - current adaptive level if available
  - recommended next action
- Add empty states for:
  - no approved plan
  - approved plan but no tasks today
  - task already completed

Recommended backend addition:

- enrich `/patient/tasks` with current adaptive level and maybe current plan metadata to avoid frontend stitching.

---

## 8. Patient Exercise Session

### Current frontend behavior

File:

- `client/app/patient/tasks/[assignmentId]/page.tsx`

What works:

- Starts a session via `/session/start`
- Loads prompts from `/patient/tasks/{assignment_id}/prompts`
- Uploads audio to `/session/{session_id}/attempt`
- Polls `/session/attempt/{attempt_id}`
- Connects to WebSocket `/ws/{patient_id}`
- Marks assignment complete

Main issues:

- Uses both WebSocket and polling without a clear ownership model
- WebSocket messages are not correlated to a specific active attempt before applying UI state
- Polling interval/timeout cleanup is fragile
- Uses generic `Record<string, unknown>` instead of a typed score contract
- Uses `window.location.href` after completion
- Does not render `scenario_context`
- Does not distinguish warmup vs exercise UI
- No resume/retry/session recovery flow
- No handling for therapist review follow-up beyond a passive banner

Why this is only partially aligned:

- The backend scoring pipeline is richer than the UI presentation.
- The UI consumes only part of the returned score and handles session state like a prototype.

Required changes:

- Build a typed session client around:
  - start session
  - submit attempt
  - poll attempt
  - complete assignment
- Standardize on one result-delivery strategy:
  - WebSocket-first with poll fallback, or
  - poll-only if real-time is not required
- Correlate score events by `attempt_id`
- Show the full score model clearly:
  - final score
  - pass/fail
  - adaptive decision
  - performance level
  - review recommended
  - fail reason
  - transcript
- Add prompt-type-aware UI:
  - warmup
  - exercise
- Add session failure states:
  - upload failed
  - analysis timeout
  - no speech detected
  - low-confidence review recommended

Production-ready target:

- Therapy session UI should behave like a robust guided workflow, not a single component with local timers.

---

## 9. Baseline Patient Flow

### Current frontend behavior

File:

- `client/app/patient/baseline/page.tsx`

What is good:

- Uses the new backend flow:
  - `/baseline/exercises`
  - `/baseline/start`
  - `/baseline/{session_id}/attempt`
  - `/baseline/attempt/{attempt_id}`
  - `/baseline/{session_id}/complete`
- Shows final score and starting level

Remaining improvements:

- Baseline exercises are flattened; section hierarchy is not really shown
- No explicit “resume baseline” behavior
- No detailed transcript/phoneme feedback history per item
- No retry-per-item workflow beyond re-recording before submit
- No final review summary across all items

Required changes:

- Preserve and display baseline section grouping
- Show progress by assessment and section, not just flat item number
- Add “retry item” and “skip item” product rules if desired
- Show final results summary:
  - baseline name
  - raw score
  - assigned level
  - maybe item-level highlights

Possible backend addition:

- therapist-facing item breakdown endpoint
- patient-facing baseline result detail endpoint

---

## 10. Patient Progress

### Current frontend behavior

File:

- `client/app/patient/progress/page.tsx`

What is good:

- Uses `/patient/progress`
- Displays total attempts, average score, pass rate, weekly trend, task metrics, dominant emotion

What is still shallow:

- Does not explain adaptive state
- Does not expose level progression over time
- Does not show frustration/engagement trends from session emotion summary
- Does not let the patient inspect progress per task deeply

Why this matters:

- The backend now maintains `patient_task_progress` and `session_emotion_summary`.
- The frontend still presents progress mostly as aggregate charts.

Required changes:

- Add per-task progress cards:
  - current level
  - total attempts
  - rolling accuracy
  - pass/fail trend
- Add emotion/engagement summaries if product-approved
- Add “how your level changes” explanation so adaptive decisions are understandable

Recommended backend addition:

- move progress API closer to the new v2 tables:
  - explicitly return session emotion summary data
  - optionally return progression timeline per task

---

## 11. Therapist Dashboard

### Current frontend behavior

File:

- `client/app/therapist/dashboard/page.tsx`

What it does:

- shows total patients
- shows approved patients
- shows pending patients

Why this is incomplete for the current backend:

- Backend runtime now produces therapist notifications.
- Backend records plan revision history.
- Backend has richer patient operational state than the dashboard exposes.

Required changes:

- Add dashboard widgets for:
  - pending approvals
  - review-flagged attempts
  - patients without baseline
  - patients with baseline but no approved plan
  - plans pending approval

Backend addition required:

- therapist notifications listing endpoint
- therapist notification mark-as-read endpoint
- optional dashboard summary endpoint that aggregates dashboard cards server-side

---

## 12. Therapist Patient Approval

### Current frontend behavior

File:

- `client/app/therapist/patients/[id]/page.tsx`

What works:

- Fetches patient and defects
- Approves with selected defects
- Rejects patient

Misalignment:

- Backend approve API accepts:
  - `defect_ids`
  - `primary_diagnosis`
  - `clinical_notes`
- Frontend only captures `defect_ids`

Required changes:

- Add approval form fields:
  - primary diagnosis
  - clinical notes
- Show assigned defects after approval using backend data
- Replace `alert`, `confirm`, and `window.location.href` with proper modal/toast/navigation patterns

Production-ready target:

- Therapist approval should feel like a clinical intake form, not a checkbox list with alert boxes.

---

## 13. Therapist Baseline View

### Current frontend behavior

File:

- `client/app/therapist/patients/[id]/baseline/page.tsx`

What it does:

- shows final baseline result if it exists

What is missing:

- no item-level breakdown
- no transcript review
- no phoneme-accuracy visibility
- no clinician note workflow

Alignment status:

- minimally aligned with current `/baseline/therapist-view/{patient_id}`
- not aligned with a production therapist review workflow

Required changes:

- Expand therapist baseline review UI to include:
  - baseline score
  - level
  - date
  - item-by-item results
  - transcript snippets
  - phoneme accuracy / fluency metrics where appropriate

Backend addition required:

- endpoint for baseline item results and attempt details

---

## 14. Therapist Plan Management

### Current frontend behavior

File:

- `client/app/therapist/patients/[id]/plan/page.tsx`

What works:

- generate plan
- fetch tasks for defects
- add task
- move task between days
- delete task
- approve plan

What is misaligned or incomplete:

- Delete-plan button exists in UI but has no backend action
- No plan revision history UI even though backend writes `plan_revision_history`
- No priority ordering within the same day
- No plan goals editor even though backend returns `goals`
- No conflict handling if drag/update fails
- No explicit status change UX for assignments
- No distinction between draft editing and approved-plan post-approval edits

Required changes:

- Remove dead “Delete Plan” button or implement real delete flow end-to-end
- Add revision history panel using a new backend endpoint
- Add assignment priority ordering, not just day moves
- Show plan metadata:
  - goals
  - status
  - week range
  - baseline level used
- Add mutation status feedback:
  - saving
  - saved
  - failed

Backend additions required for full production parity:

- plan revision history read endpoint
- delete plan endpoint if product wants it
- assignment reorder/priority update support

---

## 15. Therapist Progress View

### Current frontend behavior

File:

- `client/app/therapist/patients/[id]/progress/page.tsx`

What works:

- uses therapist progress API
- shows weekly trend and task breakdown

What is missing:

- dominant emotion is returned but not surfaced
- no session-level breakdown
- no review of flagged attempts
- no linking from progress to baseline or plan decisions

Required changes:

- surface dominant emotion and engagement risk
- show current level per task more prominently
- add drill-down from task metric to attempt/session history
- connect progress view to adaptive plan decisions

---

## Features Present In Backend But Missing In Frontend

These are the largest strategic gaps.

### Therapist notifications

Backend status:

- `therapist_notification` rows are created for:
  - patient registration
  - review-flagged therapy attempts

Frontend status:

- no notifications UI
- no notification polling
- no notification center
- no unread indicator

Required work:

- add therapist notifications panel
- add top-nav unread badge
- add mark-read/archive flow
- add deep-links from notification to patient or attempt context

Backend additions needed:

- list notifications API
- mark read API
- optional grouped notification summary API

### Plan revision history

Backend status:

- `plan_revision_history` is written on generate, add, reorder, remove, approve

Frontend status:

- completely invisible

Required work:

- show revision timeline on therapist plan page
- include action, actor, timestamp, and diff summary

Backend addition needed:

- revision history read endpoint

### Audio file lifecycle

Backend status:

- `audio_file` rows are created on therapy attempt upload

Frontend status:

- no audio management UI
- no replay UI
- no attempt media review

Possible future work:

- therapist attempt review with audio playback
- patient replay if product-approved

### Session emotion summary

Backend status:

- `session_emotion_summary` exists and is updated

Frontend status:

- not surfaced directly

Required work:

- either expose via progress endpoints
- or remove from frontend scope until product wants it

---

## Production-Readiness Gaps Beyond Pure Alignment

These are not only alignment issues. They are required for a serious application.

## 16. Data Fetching

Current:

- ad hoc `useEffect` fetching everywhere

Needed:

- React Query or equivalent
- request deduping
- cache invalidation
- retries
- stale state management
- optimistic updates for plan editing

## 17. Error Handling

Current:

- page-local error strings
- some alert/confirm usage
- some silent assumptions

Needed:

- normalized API error model
- toast system
- recoverable empty/error states
- auth-expiry handling
- upload timeout handling

## 18. Navigation And UX Consistency

Current:

- mixed `router.push`, `Link`, and `window.location.href`

Needed:

- standardized navigation via Next router/Link
- no hard browser redirects unless intentional

## 19. Type Safety

Current:

- manual duplicated interfaces

Needed:

- generated API types
- feature-level hooks
- remove page-local contract duplication

## 20. Accessibility And Clinical UX

Needed:

- keyboard-accessible forms and boards
- stronger focus states
- recording permission guidance
- clearer retry guidance for low-confidence/no-speech scenarios
- readable patient-safe copy for scores and failures

## 21. Observability

Needed:

- client-side error reporting
- upload failure tracing
- WebSocket disconnect logging
- feature analytics for completion funnels

---

## Recommended Frontend Change Plan

## Phase 1: Contract And Shell Stabilization

- Introduce typed API client generated from backend OpenAPI
- Add auth bootstrap with `/auth/me`
- Add centralized API error handling
- Replace `window.location.href`, `alert`, `confirm`
- Standardize loading, empty, and error states

## Phase 2: Patient Flow Alignment

- Refactor patient profile to remove all hardcoded values
- Upgrade task session flow to typed session state + attempt correlation
- Improve baseline sectioned UX and result summary
- Expand progress page to reflect adaptive progression more clearly

## Phase 3: Therapist Operational Alignment

- Expand patient approval form with diagnosis and clinical notes
- Add therapist notification center
- Add baseline detail review
- Add plan revision history panel
- Improve plan board persistence and conflict handling

## Phase 4: Production Hardening

- Add React Query
- Add toast system
- Add retry/reconnect logic for WebSocket/upload flows
- Add analytics and error reporting
- Add accessibility and copy review

---

## File-Level Frontend Worklist

### Core infrastructure

- `client/lib/api.ts`
- `client/lib/ws.ts`
- `client/store/auth.ts`
- `client/app/patient/layout.tsx`
- `client/app/therapist/layout.tsx`

### Patient pages

- `client/app/patient/home/page.tsx`
- `client/app/patient/profile/page.tsx`
- `client/app/patient/tasks/page.tsx`
- `client/app/patient/tasks/[assignmentId]/page.tsx`
- `client/app/patient/baseline/page.tsx`
- `client/app/patient/progress/page.tsx`

### Therapist pages

- `client/app/therapist/dashboard/page.tsx`
- `client/app/therapist/patients/[id]/page.tsx`
- `client/app/therapist/patients/[id]/baseline/page.tsx`
- `client/app/therapist/patients/[id]/plan/page.tsx`
- `client/app/therapist/patients/[id]/progress/page.tsx`

### Shared components

- `client/components/patient/Recorder.tsx`
- `client/components/patient/ScoreDisplay.tsx`
- `client/components/therapist/KanbanBoard.tsx`
- `client/components/therapist/KanbanTaskCard.tsx`
- `client/components/patient/PatientNav.tsx`
- `client/components/therapist/TherapistNav.tsx`

---

## Final Recommendation

Do not treat this as a set of isolated page fixes.

The correct path is:

1. align contracts first
2. harden auth and API handling
3. rebuild patient and therapist flows on top of typed feature modules
4. add the v2 backend surfaces that the UI still does not expose

If we do only visual page edits without changing the frontend architecture, the app will keep drifting every time backend contracts evolve.
