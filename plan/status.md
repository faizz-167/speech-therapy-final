# SpeechPath Frontend Alignment — Global Status Tracker

> Based on: `frontend-changes.md` audit  
> Last Updated: 2026-04-08 (Phase 3 + Phase 4 + Phase 5 + Phase 6 complete)  
> Source of truth for all phases and subtasks. AI agents must update this file after every change.

---

## Legend

| Symbol | Meaning |
|--------|---------|
| `NOT_STARTED` | Work has not begun |
| `IN_PROGRESS` | Currently being worked on |
| `COMPLETED` | Done and validated |
| `BLOCKED` | Cannot proceed — dependency unresolved |

---

## Phase Overview

| Phase | Title | Status | Notes |
|-------|-------|--------|-------|
| Phase 1 | Contract & Shell Stabilization | `COMPLETED` | Validated with `npx tsc --noEmit`, `npm run build`, and backend auth syntax checks on 2026-04-07 |
| Phase 2 | Patient Flow Alignment | `COMPLETED` | All subtasks validated; `npx tsc --noEmit` passes |
| Phase 3 | Therapist Operational Alignment | `COMPLETED` | All subtasks done; therapist baseline item-level review shipped after Phase 4.4 |
| Phase 4 | Backend API Extensions | `COMPLETED` | All 5 subtasks implemented |
| Phase 5 | Therapist Notifications Frontend | `COMPLETED` | All subtasks done; bell badge + polling + panel + optimistic updates + deep-links |
| Phase 6 | Production Hardening | `COMPLETED` | All subtasks done; React Query, sonner toasts, WS retry, upload/analysis timeouts, accessibility pass |

---

## Phase 1 — Contract & Shell Stabilization

| # | Subtask | Status | Notes |
|---|---------|--------|-------|
| 1.1 | Consolidate TypeScript types into domain modules | `COMPLETED` | Domain modules aligned to backend schemas and consumed across pages/components |
| 1.2 | Auth bootstrap provider — call `/auth/me` on app start | `COMPLETED` | Protected layouts wait for hydration/bootstrap before rendering and restore session via `/auth/me` + auth cookie |
| 1.3 | Centralized 401/403 handler + session expiry UX | `COMPLETED` | API client routes auth failures through a shared handler; logout clears the auth cookie |
| 1.4 | Replace `window.location.href`, `alert`, `confirm` everywhere | `COMPLETED` | No remaining `window.location.href`, `alert(`, or `confirm(` usages under `client/` |
| 1.5 | Standardize `Loading`, `Empty`, `Error` state components | `COMPLETED` | Shared UI states exported from `client/components/ui/index.ts` and adopted across app pages |

---

## Phase 2 — Patient Flow Alignment

| # | Subtask | Status | Notes |
|---|---------|--------|-------|
| 2.1 | Patient profile — remove all hardcoded values | `COMPLETED` | Best streak shows "—"; all other fields from real API data |
| 2.2 | Patient home — CTA priority logic + summary cards | `COMPLETED` | Summary row (streak+tasks), all-done celebration card, 3 parallel fetches |
| 2.3 | Patient tasks list — richer task cards + empty states | `COMPLETED` | Three distinct empty states: no plan / no tasks today / all completed |
| 2.4 | Patient exercise session — typed state, attempt correlation, full score display | `COMPLETED` | WS attempt_id correlation, no-speech guidance card, warmup label, poll timeout 60s |
| 2.5 | Baseline flow — section grouping, progress, result summary | `COMPLETED` | Section headers + progress indicator; neo-brutalist styling; result summary with name/count/level |
| 2.6 | Progress page — per-task cards + adaptive state explanation | `COMPLETED` | Per-task cards with level badge + accuracy; adaptive progression legend |

---

## Phase 3 — Therapist Operational Alignment

| # | Subtask | Status | Notes |
|---|---------|--------|-------|
| 3.1 | Patient approval form — add diagnosis + clinical notes fields | `COMPLETED` | primary_diagnosis + clinical_notes in form + POST body; ApproveRequest type added; success banner added |
| 3.2 | Therapist baseline review — item-level breakdown UI | `COMPLETED` | Summary card + item-level therapist review now uses `/baseline/therapist-view/{id}/items` with zero-item empty state |
| 3.3 | Plan management — revision history panel + remove dead delete button | `COMPLETED` | 3.3A done; 3.3B done (revision history panel loads non-blocking, collapsible); 3.3C done |
| 3.4 | Therapist progress view — surface emotion, current level per task | `COMPLETED` | Emotion & Engagement card; level badge per task row; up/down trend indicator from last_attempt_result |
| 3.5 | Therapist dashboard — add operational widgets | `COMPLETED` | 4 widgets with real data: pending approvals, without baseline, baseline+no plan, plans pending approval |

---

## Phase 4 — Backend API Extensions

| # | Subtask | Status | Notes |
|---|---------|--------|-------|
| 4.1 | Therapist notifications — list endpoint + mark-read endpoint | `COMPLETED` | GET /therapist/notifications + POST /notifications/read-all + POST /notifications/{id}/read |
| 4.2 | Plan revision history — read endpoint | `COMPLETED` | GET /plans/{plan_id}/revision-history; PlanRevisionEntryOut schema; client type added |
| 4.3 | Extended patient profile — therapist name, diagnosis, dates, best streak | `COMPLETED` | /patient/profile returns therapist_name, primary_diagnosis, best_streak, member_since via response model; patient-facing clinical_notes excluded |
| 4.4 | Baseline item results — therapist detail view endpoint | `COMPLETED` | GET /baseline/therapist-view/{patient_id}/items; BaselineItemDetailOut schema with phoneme/fluency/transcript/pass_fail |
| 4.5 | Therapist dashboard summary — aggregated server-side stats endpoint | `COMPLETED` | DashboardResponse extended with 4 server-side COUNT fields; N+1 client pattern removed |

---

## Phase 5 — Therapist Notifications Frontend

| # | Subtask | Status | Notes |
|---|---------|--------|-------|
| 5.1 | Notification center panel component | `COMPLETED` | NotificationPanel.tsx; list, unread styling, empty state, type icons, relative timestamps |
| 5.2 | Top-nav unread badge + polling | `COMPLETED` | Bell button in TherapistNav; 60s polling with interval cleanup; badge hides at 0 |
| 5.3 | Mark-read and archive flow | `COMPLETED` | Optimistic updates for individual + mark-all; revert on API error; no fake archive |
| 5.4 | Deep-link from notification to patient/attempt context | `COMPLETED` | router.push() to patient page or progress page; panel closes on nav; arrow indicator |

---

## Phase 6 — Production Hardening

| # | Subtask | Status | Notes |
|---|---------|--------|-------|
| 6.1 | Install + configure React Query; replace `useEffect` fetching | `COMPLETED` | @tanstack/react-query v5; QueryClientProvider in layout; all 10 pages migrated to useQuery/useMutation; useMutation with cache invalidation for approve/plan ops |
| 6.2 | Toast notification system (replace alert/confirm remnants) | `COMPLETED` | sonner installed; Toaster in layout with neo-brutalist style; lib/toast.ts; toast on approve/reject/plan mutations, upload errors, reconnect events, analysis timeout |
| 6.3 | WebSocket retry / reconnect logic | `COMPLETED` | ws.ts: 5-attempt cap, 2s delay, re-auth on reconnect, onReconnect/onFallback callbacks, clean disconnect(); exercise page shows reconnecting/polling-mode indicators |
| 6.4 | Upload failure + analysis timeout UX handling | `COMPLETED` | 30s upload timeout via api.upload timeout option; 90s analysis timeout (45×2s) with "saved, therapist notified" message; AbortError mapped to clear message; retry re-opens recorder |
| 6.5 | Accessibility pass — keyboard nav, focus states, patient-safe copy | `COMPLETED` | KeyboardSensor added to KanbanBoard; Recorder buttons have aria-label + role=status; ScoreDisplay "FAIL"→"Not quite — keep going!"; baseline "failed"→"Try Again / Speech clarity needs practice"; form inputs have id+label associations |
