# Phase 6 — Production Hardening

## Objective

Harden the frontend for real-world use. Replace ad hoc `useEffect` data fetching with React Query, add a proper toast system, add WebSocket resilience, handle upload failure scenarios cleanly, and complete an accessibility pass.

## Dependencies

- Phases 1–5 must be completed.
- All page-level data fetching, navigation, and error patterns from earlier phases must be settled before wrapping them in React Query (otherwise React Query migrations conflict with in-flight changes).

---

## Subtasks

### 6.1 — React Query Integration (Replace `useEffect` Fetching)

**Problem (from frontend-changes.md §16):**  
Every page fetches data via ad hoc `useEffect` + `useState`. There is no request deduplication, cache invalidation, retry, or stale state management.

**Execution steps:**
1. Install React Query:
   ```bash
   cd client && npm install @tanstack/react-query
   ```
2. Wrap the root layout (`client/app/layout.tsx`) with `<QueryClientProvider>`.
3. Create `client/lib/queryClient.ts` — configure `QueryClient` with sensible defaults:
   - `staleTime: 30_000` (30s)
   - `retry: 2`
   - `refetchOnWindowFocus: false` (avoids over-fetching in a clinical app)
4. For each page that uses `useEffect` + `useState` to fetch data, replace with `useQuery`:
   - Define a query key per domain: `['patient', 'profile']`, `['therapist', 'patients']`, etc.
   - Move the `get<T>(...)` call into the `queryFn`.
   - Remove the `useEffect` + `loading/error` state boilerplate.
   - The `<LoadingState />` and `<ErrorState />` components from Phase 1 still apply — wire them to `isLoading` and `isError` from `useQuery`.
5. For mutation operations (approve, plan edits, mark notification read), replace with `useMutation` + `queryClient.invalidateQueries(...)` for cache invalidation.
6. Priority order for migration (most impactful first):
   - `therapist/dashboard/page.tsx`
   - `therapist/patients/page.tsx`
   - `patient/home/page.tsx`
   - `patient/tasks/page.tsx`
   - `patient/progress/page.tsx`
   - Remaining pages.

**Validation criteria:**
- No `useEffect` + `useState` data fetching pattern remains in any page (grep for `useEffect` and check each instance).
- Navigating away and back to a page uses the cache without re-fetching (within stale time).
- A mutation (e.g., approving a patient) automatically refreshes the affected query.
- `npx tsc --noEmit` passes.

---

### 6.2 — Toast Notification System

**Problem (from frontend-changes.md §17):**  
Success and error messages are shown via inline banners (added in earlier phases) or were previously `alert()`. A proper toast system unifies feedback across all pages.

**Execution steps:**
1. Choose a toast library compatible with Next.js App Router:
   - Recommended: `sonner` (lightweight, no SSR issues).
   - Install: `npm install sonner`.
2. Add `<Toaster />` to `client/app/layout.tsx`.
3. Create `client/lib/toast.ts` — re-export `toast.success`, `toast.error`, `toast.info` from `sonner` so callers don't import `sonner` directly.
4. Audit all inline banner state (`const [banner, setBanner] = useState<string | null>(null)`) introduced in earlier phases and replace with `toast.success(message)` or `toast.error(message)`.
5. Also replace in:
   - Plan mutation feedback (saving/saved/failed from Phase 3.3).
   - Notification mark-read errors (Phase 5.3).
   - Auth expiry message (Phase 1.3).
6. Style `<Toaster />` to match the neo-brutalist palette (black border, white bg, bold font).

**Validation criteria:**
- No inline banner `useState` pattern remains for success/error feedback.
- Toast appears on: patient approval, plan approval, auth expiry, upload failure, baseline completion.
- Toast styling matches the neo-brutalist design language.
- `npx tsc --noEmit` passes.

---

### 6.3 — WebSocket Retry / Reconnect Logic

**Problem (from frontend-changes.md §18 and context.md known issues):**  
WebSocket disconnects are not automatically recovered. If the connection drops mid-session (network hiccup), the patient receives no score and the session stalls.

**File:** `client/lib/ws.ts`  
**File:** `client/app/patient/tasks/[assignmentId]/page.tsx`

**Execution steps:**
1. Read `client/lib/ws.ts` — understand the current `createWebSocket` factory.
2. Add reconnect logic to `createWebSocket`:
   - On `onclose` event (that is not a clean intentional close): wait 2 seconds, then reconnect.
   - Track reconnect attempt count; cap at 5 attempts.
   - On each reconnect, re-send the auth message (`{"type":"auth","token":"..."}`) after connection opens.
   - Emit a callback (`onReconnect`) so the calling page can show a "Reconnecting..." status.
3. In the exercise session page:
   - Show a subtle "Reconnecting to score delivery..." indicator when WebSocket is reconnecting.
   - Show "Live scoring unavailable — using fallback polling" if all reconnect attempts fail.
   - Fall back to polling-only if WebSocket fails after all retries.
4. Add a `disconnect()` function to cleanly close without triggering reconnect.

**Validation criteria:**
- Simulating a WebSocket disconnect (by temporarily stopping Redis or the server) triggers automatic reconnect.
- Reconnect counter caps at 5 and falls back to poll-only.
- No infinite reconnect loop.
- Intentional close (navigate away, component unmount) does not trigger reconnect.

---

### 6.4 — Upload Failure + Analysis Timeout UX Handling

**Problem (from frontend-changes.md §8 and context.md):**  
Upload failures and Celery analysis timeouts have no structured UX. The patient is left staring at a spinner indefinitely.

**File:** `client/app/patient/tasks/[assignmentId]/page.tsx`  
**File:** `client/app/patient/baseline/page.tsx`

**Execution steps:**
1. Add upload timeout:
   - If the `POST /session/{id}/attempt` (or `/baseline/{id}/attempt`) call does not complete within 30 seconds, abort it and show a retry state.
   - Use `AbortController` with a 30-second timeout passed to `fetch`.
2. Add analysis timeout:
   - If polling `GET /session/attempt/{id}` runs for more than 90 seconds without a result, stop polling and show: "Analysis is taking longer than expected. Your attempt was saved — your therapist will be notified."
   - This prevents infinite polling.
3. Add no-speech detection:
   - The backend returns a specific `fail_reason` when no speech is detected. Map this to a patient-safe message: "We couldn't detect speech in your recording. Please try again in a quieter environment."
4. Add retry button on upload failure that re-records (does not re-use the failed audio blob).

**Validation criteria:**
- Upload that never completes shows a timeout error after 30 seconds.
- Poll that never resolves stops after 90 seconds with a "saved, therapist notified" message.
- `fail_reason: "no_speech"` maps to a human-readable guidance card.
- Retry button re-opens the recorder.

---

### 6.5 — Accessibility Pass

**Problem (from frontend-changes.md §20):**  
Forms, the Kanban board, the recorder, and score display are not verified to be keyboard-accessible. Clinical applications must meet basic accessibility standards.

**Execution steps:**
1. **Forms and inputs:**
   - Every `<NeoInput>` and `<NeoSelect>` must have a visible `<label>` (not just placeholder).
   - All buttons must have descriptive `aria-label` if the label text is ambiguous.
2. **Kanban board:**
   - Verify `@dnd-kit` is configured with keyboard sensor (`KeyboardSensor`) in `KanbanBoard.tsx`.
   - Task cards must be focusable and moveable by keyboard.
3. **Recorder:**
   - Mic permission error shows a clear text message, not just an icon.
   - Record and Stop buttons have `aria-label="Start recording"` / `aria-label="Stop recording"`.
4. **Score display:**
   - Scores are readable as text (not only as colors or bars).
   - Pass/fail states use both color AND text/icon — not color alone.
5. **Focus states:**
   - Verify that all interactive elements have visible `:focus-visible` outlines.
   - Do not remove `outline: none` without replacing with an equivalent focus indicator.
6. **Patient-safe copy review:**
   - Score failure messages should not use alarming clinical language.
   - "Failed" → "Not quite" or "Try again".
   - "Low phoneme accuracy" → "Speech clarity needs practice".
   - Review all score-related messages for tone.

**Validation criteria:**
- All form inputs have associated labels.
- Kanban board tasks are keyboard-moveable.
- Recorder buttons have `aria-label`.
- Pass/fail is communicated by text, not color alone.
- All patient-facing failure messages use supportive language.

---

## Execution Order

```
6.1 (React Query) — highest impact, do first
6.2 (toast) — can run in parallel with 6.1
6.3 (WebSocket retry) — independent, run in parallel
6.4 (upload/timeout) — independent, run in parallel with 6.1–6.3
6.5 (accessibility) — run last as a final pass
```

## Validation Criteria (Phase Complete)

- [ ] No `useEffect` + `useState` data fetching pattern in any page.
- [ ] Toast system is wired up across all mutation/error flows.
- [ ] WebSocket reconnects automatically up to 5 times, then falls back to polling.
- [ ] Upload timeout (30s) and analysis timeout (90s) show specific user-facing states.
- [ ] `fail_reason: "no_speech"` renders a patient-safe guidance message.
- [ ] All forms have visible labels.
- [ ] Kanban board is keyboard-accessible.
- [ ] All score/result feedback uses language that is supportive and non-alarming.
- [ ] `npx tsc --noEmit` passes.
- [ ] `npm run build` produces no errors.
