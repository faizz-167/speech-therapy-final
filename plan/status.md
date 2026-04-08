# SpeechPath Frontend Alignment — Global Status Tracker

> Based on: `frontend-changes.md` audit  
> Last Updated: 2026-04-08  
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
| Phase 3 | Therapist Operational Alignment | `IN_PROGRESS` | 3.1/3.3/3.4/3.5 done; 3.2 and 3.3B blocked on Phase 4 |
| Phase 4 | Backend API Extensions | `NOT_STARTED` | Unlocks Phase 5 features |
| Phase 5 | Therapist Notifications Frontend | `NOT_STARTED` | Depends on Phase 4 |
| Phase 6 | Production Hardening | `NOT_STARTED` | Depends on Phase 1–5 |

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
| 3.2 | Therapist baseline review — item-level breakdown UI | `BLOCKED` | therapist-view endpoint returns top-level summary only; blocked on Phase 4.4 (baseline item results endpoint) |
| 3.3 | Plan management — revision history panel + remove dead delete button | `IN_PROGRESS` | 3.3A done (delete button removed); 3.3B BLOCKED on Phase 4.2; 3.3C done (goals display + mutation saving/saved/failed feedback) |
| 3.4 | Therapist progress view — surface emotion, current level per task | `COMPLETED` | Emotion & Engagement card; level badge per task row; up/down trend indicator from last_attempt_result |
| 3.5 | Therapist dashboard — add operational widgets | `COMPLETED` | 4 widgets with real data: pending approvals, without baseline, baseline+no plan, plans pending approval |

---

## Phase 4 — Backend API Extensions

| # | Subtask | Status | Notes |
|---|---------|--------|-------|
| 4.1 | Therapist notifications — list endpoint + mark-read endpoint | `NOT_STARTED` | |
| 4.2 | Plan revision history — read endpoint | `NOT_STARTED` | |
| 4.3 | Extended patient profile — therapist name, diagnosis, dates, best streak | `NOT_STARTED` | |
| 4.4 | Baseline item results — therapist detail view endpoint | `NOT_STARTED` | |
| 4.5 | Therapist dashboard summary — aggregated server-side stats endpoint | `NOT_STARTED` | |

---

## Phase 5 — Therapist Notifications Frontend

| # | Subtask | Status | Notes |
|---|---------|--------|-------|
| 5.1 | Notification center panel component | `NOT_STARTED` | Requires Phase 4.1 |
| 5.2 | Top-nav unread badge + polling | `NOT_STARTED` | Requires Phase 4.1 |
| 5.3 | Mark-read and archive flow | `NOT_STARTED` | Requires Phase 4.1 |
| 5.4 | Deep-link from notification to patient/attempt context | `NOT_STARTED` | Requires Phase 5.1–5.3 |

---

## Phase 6 — Production Hardening

| # | Subtask | Status | Notes |
|---|---------|--------|-------|
| 6.1 | Install + configure React Query; replace `useEffect` fetching | `NOT_STARTED` | |
| 6.2 | Toast notification system (replace alert/confirm remnants) | `NOT_STARTED` | |
| 6.3 | WebSocket retry / reconnect logic | `NOT_STARTED` | |
| 6.4 | Upload failure + analysis timeout UX handling | `NOT_STARTED` | |
| 6.5 | Accessibility pass — keyboard nav, focus states, patient-safe copy | `NOT_STARTED` | |
