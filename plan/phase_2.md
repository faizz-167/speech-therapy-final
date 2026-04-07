# Phase 2 — Patient Flow Alignment

## Objective

Bring every patient-facing page into full alignment with the current backend. Remove all hardcoded values, improve session state handling, surface adaptive progression data, and complete the baseline flow UX.

## Dependencies

- Phase 1 must be completed (shared types, auth bootstrap, shared state components, router/nav patterns).

---

## Subtasks

### 2.1 — Patient Profile — Remove All Hardcoded Values

**Problem (from frontend-changes.md §6):**  
Therapist name is hardcoded as `Faiz`, diagnosis as `—`, member-since as `01/04/2026`, and best streak duplicates current streak. The backend does not currently return all these fields.

**File:** `client/app/patient/profile/page.tsx`

**Execution steps:**
1. Read the current `/patient/profile` API response shape from `server/app/routers/patient.py` and `server/app/schemas/`.
2. For fields NOT currently returned by the backend (therapist name, primary diagnosis, created_at, best streak):
   - Display `—` or `Not available` with a visually distinct style so it is clear the data is absent, not a bug.
   - Do NOT invent data.
3. Remove all hardcoded string literals for `Faiz`, `01/04/2026`, diagnosis.
4. Map real fields from the API response: `defects`, `current_streak`, `total_sessions`, etc.
5. Add `<LoadingState />` and `<ErrorState />` from Phase 1.
6. Use types from `client/types/patient.ts`.

**Validation criteria:**
- No hardcoded personal data strings appear in the file.
- The page renders with real API data, clearly marking any absent fields.

---

### 2.2 — Patient Home — CTA Priority Logic + Summary Cards

**Problem (from frontend-changes.md §5):**  
Home page has basic state handling but lacks CTA priority logic, streak display, and progress summary.

**File:** `client/app/patient/home/page.tsx`

**Execution steps:**
1. Read the `/patient/home` endpoint response (check `server/app/routers/patient.py`).
2. Implement CTA priority waterfall:
   - Baseline NOT completed → show baseline CTA card prominently.
   - Baseline complete + no approved plan → show "Waiting for your therapist to review your plan" state.
   - Approved plan + remaining tasks today → show "Resume today's tasks" CTA with task count.
   - All tasks done → show completion celebration card.
3. Add summary cards row:
   - Current streak (from profile or home response).
   - Today's task count (from home response).
   - Latest baseline level (from home or baseline response).
4. Use `<LoadingState />`, `<EmptyState />`, `<ErrorState />` from Phase 1.
5. Use types from `client/types/patient.ts`.

**Validation criteria:**
- Each CTA state renders correctly based on backend data.
- No hardcoded mock values.
- Page does not crash when any field is `null` or `undefined`.

---

### 2.3 — Patient Tasks List — Richer Task Cards + Empty States

**Problem (from frontend-changes.md §7):**  
Task cards show minimal info; no adaptive level, no completion status, no empty states for edge cases.

**File:** `client/app/patient/tasks/page.tsx`

**Execution steps:**
1. Read the `/patient/tasks` endpoint shape. Note which fields are available (task name, mode, completion status, assignment ID).
2. Update each task card to display:
   - Task name and mode.
   - Completion status (completed / in-progress / not started) with a distinct badge.
   - Adaptive level if available in the response (`current_level` or equivalent).
3. Add empty states for:
   - No approved plan exists → "Your therapist hasn't approved a plan yet."
   - Plan approved but no tasks scheduled today → "No tasks scheduled for today — check back tomorrow."
   - All today's tasks are completed → "You've finished all tasks for today!"
4. Use `<EmptyState />` component from Phase 1 for each case.
5. Use types from `client/types/patient.ts`.

**Validation criteria:**
- All three empty states render correctly.
- Task cards show completion status and level when available.

---

### 2.4 — Patient Exercise Session — Typed State, Attempt Correlation, Full Score Display

**Problem (from frontend-changes.md §8):**  
Session page uses `Record<string, unknown>` for scores, mixes WebSocket and polling without clear ownership, does not correlate score events to `attempt_id`, and uses `window.location.href` post-completion.

**File:** `client/app/patient/tasks/[assignmentId]/page.tsx`  
**File:** `client/components/patient/ScoreDisplay.tsx`

**Execution steps:**
1. Define a typed `SessionState` machine in a local `useSessionFlow` hook:
   ```
   idle → session_starting → session_active → attempt_recording →
   attempt_uploading → awaiting_score → score_received → assignment_complete
   ```
2. Define a typed `AttemptScore` interface in `client/types/session.ts` covering:
   - `final_score`, `pass_fail`, `adaptive_decision`, `performance_level`
   - `review_recommended`, `fail_reason`, `transcript`
   - `phoneme_accuracy`, `word_accuracy`, `fluency_score`
3. Standardize on **WebSocket-first, poll fallback** strategy:
   - Start polling at 2s interval immediately after upload.
   - If WebSocket delivers the score first, cancel poll and update state.
   - If poll returns a completed status first, cancel WS listener.
   - Correlate by `attempt_id`: only accept score updates whose `attempt_id` matches the currently active attempt.
4. Poll cleanup: clear intervals in `useEffect` cleanup functions.
5. Replace `window.location.href` post-completion → `router.push('/patient/tasks')`.
6. Expand `<ScoreDisplay />` to render all fields from `AttemptScore`.
7. Add failure states:
   - Upload failed → `<ErrorState message="Upload failed. Please try again." onRetry={retryUpload} />`.
   - Analysis timeout (poll > 60s with no result) → timeout error state.
   - No speech detected (returned from backend) → specific guidance card.
8. Add prompt-type awareness: show warmup vs exercise label based on `prompt.prompt_type`.

**Validation criteria:**
- `Record<string, unknown>` is gone; all score data is typed.
- Attempt correlation works: a stale WS message from a previous attempt does not overwrite the current score.
- Poll cleanup: no memory leak when navigating away during polling.
- All failure states render correctly.
- `window.location.href` is gone from this file.

---

### 2.5 — Baseline Flow — Section Grouping, Progress, Result Summary

**Problem (from frontend-changes.md §9):**  
Baseline exercises are flattened; section hierarchy is invisible. No final review summary. No per-section progress.

**File:** `client/app/patient/baseline/page.tsx`

**Execution steps:**
1. Read the `/baseline/exercises` response — note if it returns `section` groupings (check `server/app/routers/baseline.py` and `server/app/schemas/`).
2. Group exercises by section before rendering. Show section name as a heading between groups.
3. Add section progress indicator: "Section 2 of 4 — Fluency Exercises (3/5 items done)".
4. Show overall baseline progress: "Item 7 of 14" above the recorder.
5. On `baseline/complete`, show a final summary card:
   - Baseline name.
   - Raw score.
   - Assigned starting level (easy / medium / advanced).
   - Optional: item count completed.
6. Add a "Resume Baseline" behavior: if an in-progress baseline session ID is stored in state, prompt to resume rather than starting fresh.
7. Use types from `client/types/baseline.ts`.

**Validation criteria:**
- Section hierarchy is visually visible in the UI.
- Overall progress counter renders correctly.
- Final summary card shows real score + level from the backend response.
- Resuming mid-baseline does not create a duplicate session.

---

### 2.6 — Progress Page — Per-Task Cards + Adaptive State Explanation

**Problem (from frontend-changes.md §10):**  
Progress is displayed as aggregate charts only. Adaptive progression state is not explained. No per-task breakdown.

**File:** `client/app/patient/progress/page.tsx`

**Execution steps:**
1. Read the `/patient/progress` endpoint response — confirm it returns `task_metrics` with per-task data.
2. Add a "My Tasks" section below the aggregate charts with per-task cards showing:
   - Task name.
   - Current adaptive level (easy / medium / advanced).
   - Total attempts.
   - Pass rate (percentage).
   - Last attempt result (pass / fail badge).
3. Add an "Adaptive Progression" explanation panel:
   - Score ≥ 75 → level advances.
   - Score 55–74 → stays at current level.
   - Score < 55 → drops to easier level.
   - Display as a simple visual legend or info card.
4. Surface dominant emotion from the response if available (check if `dominant_emotion` or `emotion_trend` fields exist in the progress response).
5. Add `<EmptyState />` for when no attempts have been made yet.
6. Use types from `client/types/progress.ts`.

**Validation criteria:**
- Per-task cards render for every task returned by the API.
- Adaptive progression explanation is visible.
- Emotion data is shown if the backend returns it.
- Page handles zero-attempt state gracefully.

---

## Execution Order

```
2.1 (profile) and 2.2 (home) can run in parallel
2.3 (tasks list) can run in parallel with 2.1 and 2.2
2.4 (exercise session) requires 2.3 to be done first
2.5 (baseline) is independent — can run in parallel with 2.1–2.3
2.6 (progress) is independent — can run in parallel with any other subtask
```

## Validation Criteria (Phase Complete)

- [ ] No hardcoded personal data in any patient page.
- [ ] CTA priority logic renders correct state on the home page.
- [ ] All three task list empty states render correctly.
- [ ] Exercise session uses typed score, attempt correlation, and WebSocket-first + poll-fallback.
- [ ] Baseline shows section grouping and result summary.
- [ ] Progress page shows per-task cards and adaptive level explanation.
- [ ] `npx tsc --noEmit` passes after all changes.
