# Phase 3 — Therapist Operational Alignment

## Objective

Bring every therapist-facing page into full alignment with the backend's current operational model. Surface data and workflows that the backend already supports but the frontend currently ignores.

## Dependencies

- Phase 1 must be completed.
- Phase 4 (backend extensions) must be completed for subtasks 3.2 (baseline item detail) and 3.3 (revision history). Subtasks 3.1, 3.4, and 3.5 can proceed independently.

---

## Subtasks

### 3.1 — Patient Approval Form — Add Diagnosis + Clinical Notes Fields

**Problem (from frontend-changes.md §12):**  
Backend `approve` endpoint accepts `defect_ids`, `primary_diagnosis`, and `clinical_notes` — but the frontend only sends `defect_ids`. Clinical context is silently discarded.

**File:** `client/app/therapist/patients/[id]/page.tsx`

**Execution steps:**
1. Read the current approve flow in the file. Identify the form state and the POST call.
2. Add two new form fields to the approval form:
   - `primary_diagnosis` — `<NeoInput>` or `<textarea>` labeled "Primary Diagnosis".
   - `clinical_notes` — `<textarea>` labeled "Clinical Notes (optional)".
3. Include both new fields in the POST body sent to `/therapist/patients/{id}/approve`.
4. Update the `ApproveRequest` type in `client/types/therapist.ts` to include these fields.
5. Replace the existing `confirm()` dialog for rejection with `<ConfirmModal />` from Phase 1.
6. Replace `alert()` success/error messages with inline banner state or toast (Phase 6.2 will upgrade to proper toast; for now use a banner).
7. After approval, navigate with `router.push()` instead of `window.location.href`.
8. Show assigned defects as read-only chips after approval is confirmed.

**Validation criteria:**
- `primary_diagnosis` and `clinical_notes` are included in the approve API call.
- No `alert()`, `confirm()`, or `window.location.href` in the file.
- `<ConfirmModal />` is used for the reject action.
- Form validates that at least one defect is selected before approving.

---

### 3.2 — Therapist Baseline Review — Item-Level Breakdown UI

**Problem (from frontend-changes.md §13):**  
Current page shows only the final baseline result. Therapists need item-level scores, transcripts, and phoneme metrics.

**File:** `client/app/therapist/patients/[id]/baseline/page.tsx`

**Execution steps:**
1. Check whether `GET /baseline/therapist-view/{patient_id}` already returns item-level data. Read `server/app/routers/baseline.py`.
2. **If the endpoint already returns item results:** Map them into the UI (skip to step 5).
3. **If not:** This subtask is `BLOCKED` on Phase 4.4 (baseline item results endpoint). Mark it `BLOCKED` in `status.md`.
4. Once the endpoint is available, define `BaselineItemResult` type in `client/types/baseline.ts`.
5. Expand the page to show:
   - Top-level summary: baseline name, date, overall score, assigned level.
   - Expandable or tabbed item list:
     - Item prompt text.
     - Patient transcript snippet (from Whisper output).
     - Phoneme accuracy score.
     - Fluency score.
     - Final item score.
     - Pass / fail badge.
6. Use `<LoadingState />` and `<ErrorState />` from Phase 1.

**Validation criteria:**
- Item-level breakdown is visible and accurate for at least the test data.
- Page handles zero-item state (no baseline completed yet).
- Transcript and phoneme data display correctly when available.

---

### 3.3 — Plan Management — Revision History Panel + Remove Dead Delete Button

**Problem (from frontend-changes.md §14):**  
Backend writes `plan_revision_history` on every edit action but the frontend never shows it. A "Delete Plan" button exists in UI with no backend action.

**File:** `client/app/therapist/patients/[id]/plan/page.tsx`

**Execution steps:**

**Part A — Remove dead Delete button:**
1. Locate the "Delete Plan" button in the file.
2. Either remove it entirely or replace it with a disabled state with tooltip "Not available" until a delete endpoint exists.
3. Do NOT implement a fake delete that doesn't call the backend.

**Part B — Revision History Panel (requires Phase 4.2):**
1. Once `GET /plans/{plan_id}/revision-history` is available (Phase 4.2), add a collapsible sidebar or bottom panel labeled "Revision History".
2. Each history entry shows:
   - Action type (generated / task_added / task_removed / task_reordered / approved).
   - Actor name (therapist).
   - Timestamp (human-readable, e.g., "2 hours ago").
   - Optional diff summary if returned by backend.
3. Load revision history via a separate API call after the plan loads (do not block the plan UI on it).
4. Define `PlanRevisionEntry` type in `client/types/plans.ts`.

**Part C — Plan metadata display:**
1. Show plan metadata above the Kanban board:
   - Plan status badge (draft / approved).
   - Week range (start_date → end_date).
   - Baseline level used for plan generation.
   - Plan goals if the backend returns them.
2. Add mutation status feedback on drag/drop/add/remove:
   - While saving → show a subtle "Saving..." indicator.
   - On success → show "Saved" with a checkmark for 2 seconds.
   - On failure → show an inline error banner.

**Validation criteria:**
- Dead delete button is removed or clearly disabled.
- Revision history panel loads and displays after plan loads (non-blocking).
- Plan metadata (status, week range, baseline level) is visible above the board.
- Mutation feedback (saving/saved/failed) is visible on every drag/add/remove action.

---

### 3.4 — Therapist Progress View — Surface Emotion, Current Level Per Task

**Problem (from frontend-changes.md §15):**  
Dominant emotion is returned but not displayed. Current level per task is not prominent. No session-level breakdown.

**File:** `client/app/therapist/patients/[id]/progress/page.tsx`

**Execution steps:**
1. Read the therapist progress endpoint `GET /therapist/patients/{patient_id}/progress` — confirm which fields are returned.
2. Add an "Emotion & Engagement" card if `dominant_emotion` or emotion data is present:
   - Dominant emotion badge.
   - Engagement risk flag if engagement score < 35.
3. Upgrade task metrics section:
   - Show `current_level` prominently (as a badge: Easy / Medium / Advanced) on each task row.
   - Add a mini trend indicator (up/down arrow) based on recent pass rate.
4. Connect the progress view to adaptive decisions:
   - Add a "Plan Decisions" card that summarizes whether any task levels recently changed based on scoring.
5. Use types from `client/types/progress.ts` and `client/types/therapist.ts`.

**Validation criteria:**
- Dominant emotion is displayed when returned by the API.
- Each task row shows its current adaptive level.
- Page handles absent emotion data gracefully (no crash, no blank widget).

---

### 3.5 — Therapist Dashboard — Operational Widgets

**Problem (from frontend-changes.md §11):**  
Dashboard only shows total/approved/pending patient counts. Backend runtime now produces richer operational state that goes unused.

**File:** `client/app/therapist/dashboard/page.tsx`

**Execution steps:**
1. Read the current dashboard API response from `GET /therapist/dashboard`.
2. Add operational widgets (using data already returned or derivable):
   - **Pending Approvals** — count of pending patients with a quick-approve CTA linking to `/therapist/patients`.
   - **Patients Without Baseline** — count; links to patient list filtered by this state.
   - **Patients With Baseline But No Approved Plan** — count; CTA to generate plan.
   - **Plans Pending Approval** — count of `draft` plans.
3. Each widget uses `NeoCard` with a count, a label, and an optional action link.
4. Notifications widget will be added in Phase 5 (after backend endpoint is ready).
5. Use `<LoadingState />` and `<ErrorState />` from Phase 1.

**Note:** If the current `/therapist/dashboard` endpoint does not return all needed data, derive what is available from `/therapist/patients` response. The dedicated dashboard summary endpoint is Phase 4.5.

**Validation criteria:**
- All four operational widgets render with real backend data.
- Each widget links to the relevant action page.
- No hardcoded counts in the UI.

---

## Execution Order

```
3.1 (approval form) — independent, start immediately
3.4 (progress view) — independent, start immediately
3.5 (dashboard) — independent, start immediately
3.2 (baseline detail) — BLOCKED until Phase 4.4 ships
3.3 Part A (delete button) — independent, start immediately
3.3 Part B (revision history) — BLOCKED until Phase 4.2 ships
3.3 Part C (plan metadata) — independent, start immediately
```

## Validation Criteria (Phase Complete)

- [ ] Approval form sends `primary_diagnosis` and `clinical_notes` to the backend.
- [ ] Therapist baseline review shows item-level breakdown.
- [ ] Dead "Delete Plan" button is removed or disabled.
- [ ] Plan revision history panel loads (non-blocking) from backend.
- [ ] Plan mutation feedback (saving/saved/failed) is visible.
- [ ] Therapist progress view shows emotion data and per-task current level.
- [ ] Dashboard shows all four operational widgets with real data.
- [ ] No `alert()`, `confirm()`, or `window.location.href` in any therapist page.
- [ ] `npx tsc --noEmit` passes.
