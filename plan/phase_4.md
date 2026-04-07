# Phase 4 — Backend API Extensions

## Objective

Implement the new backend endpoints required to complete the therapist-facing features in Phase 3 and 5. These are all additive changes — no existing endpoints are modified.

## Dependencies

- Backend is running (FastAPI + PostgreSQL + Celery).
- Phase 1 types work is conceptually useful but not technically blocking.
- Each subtask in this phase is independent of the others.

---

## Subtasks

### 4.1 — Therapist Notifications API

**New endpoints:**
- `GET /therapist/notifications` — list unread/all notifications for the current therapist
- `POST /therapist/notifications/{id}/read` — mark one notification as read
- `POST /therapist/notifications/read-all` — mark all as read

**Context:**  
The `therapist_notification` table already exists (from `server/app/models/operations.py`). Rows are created when a patient registers and when a therapy attempt is flagged for review. The table has not yet been exposed via any API.

**Execution steps:**
1. Read `server/app/models/operations.py` — understand `TherapistNotification` columns (id, therapist_id, patient_id, attempt_id, notification_type, message, is_read, created_at).
2. Add schemas to `server/app/schemas/` — create `NotificationOut`, `NotificationListOut`.
3. Add three route handlers to `server/app/routers/therapist.py` (or create `server/app/routers/notifications.py`):
   - `GET /therapist/notifications` — query all notifications for `current_therapist.id`, ordered by `created_at DESC`, with optional `?unread_only=true` filter.
   - `POST /therapist/notifications/{id}/read` — set `is_read = True` for the given notification ID (verify it belongs to current therapist).
   - `POST /therapist/notifications/read-all` — set `is_read = True` for all notifications of current therapist.
4. Register the new router in `server/app/main.py` if a new file is created.
5. Test with curl or the FastAPI docs UI at `http://localhost:8000/docs`.

**Pydantic schema shape:**
```python
class NotificationOut(BaseModel):
    id: int
    notification_type: str
    message: str
    is_read: bool
    created_at: datetime
    patient_id: int | None
    attempt_id: int | None

    model_config = ConfigDict(from_attributes=True)
```

**Validation criteria:**
- `GET /therapist/notifications` returns a list (empty if none) without 500 error.
- `POST /therapist/notifications/{id}/read` sets `is_read` to true.
- A therapist cannot mark another therapist's notification as read (403).
- FastAPI `/docs` shows all three endpoints.

---

### 4.2 — Plan Revision History Read Endpoint

**New endpoint:**
- `GET /plans/{plan_id}/revision-history` — returns all revision history entries for the given plan

**Context:**  
`plan_revision_history` rows are already written by `server/app/routers/plans.py` on generate, add, reorder, remove, and approve events. The table has not been exposed for reading.

**Execution steps:**
1. Read `server/app/models/plan.py` — understand `PlanRevisionHistory` columns (id, plan_id, action, actor_id, actor_role, change_summary, created_at).
2. Add `PlanRevisionEntryOut` schema to `server/app/schemas/`.
3. Add route handler to `server/app/routers/plans.py`:
   - `GET /plans/{plan_id}/revision-history`
   - Verify the plan belongs to a patient of the current therapist.
   - Return all entries ordered by `created_at ASC`.
4. Test via `/docs`.

**Pydantic schema shape:**
```python
class PlanRevisionEntryOut(BaseModel):
    id: int
    action: str
    actor_role: str
    change_summary: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

**Validation criteria:**
- `GET /plans/{plan_id}/revision-history` returns a list of entries.
- Therapist cannot access revision history for another therapist's patient's plan.
- Entries are ordered chronologically.

---

### 4.3 — Extended Patient Profile Endpoint

**Problem:**  
`GET /patient/profile` currently does not return `therapist_name`, `primary_diagnosis`, `created_at`, or `best_streak`. The patient profile page needs real data for all displayed fields.

**Approach:**  
Extend the existing `/patient/profile` response schema, or add a companion endpoint. Prefer extending the existing endpoint to avoid extra API calls.

**Execution steps:**
1. Read `server/app/routers/patient.py` — find the `/patient/profile` handler.
2. Join to the `Therapist` table on `patient.therapist_id` to retrieve `therapist.full_name`.
3. Return `patient.primary_diagnosis` and `patient.clinical_notes` (set during therapist approval — verify the column exists in `server/app/models/users.py`).
4. Return `patient.created_at` as `member_since`.
5. Return `patient.best_streak` if the column exists; otherwise add a `best_streak` column to the `Patient` model and update `reset_db.py` accordingly.
6. Update the `PatientProfileOut` Pydantic schema to include all new fields.
7. Update `client/types/patient.ts` `PatientProfile` interface to match.

**Note:** Do NOT run Alembic migrations. Use `reset_db.py` to reset and reseed if schema changes are needed.

**Validation criteria:**
- `GET /patient/profile` returns `therapist_name`, `primary_diagnosis`, `member_since`, `best_streak`.
- All fields are non-null when the patient has been approved with a complete profile.
- `client/types/patient.ts` is updated to match.

---

### 4.4 — Baseline Item Results Endpoint for Therapist Review

**New endpoint:**
- `GET /baseline/therapist-view/{patient_id}/items` — returns item-level detail for the patient's completed baseline

**Context:**  
`baseline_item_result` rows are created during baseline completion (`server/app/routers/baseline.py`). Therapist-facing breakdown has not been implemented.

**Execution steps:**
1. Read `server/app/models/baseline.py` — understand `BaselineItemResult` columns (id, session_id, baseline_item_id, final_score, transcript, phoneme_accuracy, fluency_score, pass_fail, created_at).
2. Read `server/app/routers/baseline.py` — find `GET /baseline/therapist-view/{patient_id}`. Either extend it to include item results, or add a new route `/baseline/therapist-view/{patient_id}/items`.
3. Add `BaselineItemResultOut` schema.
4. The handler must:
   - Verify the patient belongs to the current therapist.
   - Load the latest completed baseline session for the patient.
   - Return all `BaselineItemResult` rows for that session.
5. Include `baseline_item.prompt_text` (or equivalent display text) in the response via a join.

**Pydantic schema shape:**
```python
class BaselineItemResultOut(BaseModel):
    item_id: int
    prompt_text: str
    transcript: str | None
    phoneme_accuracy: float | None
    fluency_score: float | None
    final_score: float
    pass_fail: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

**Validation criteria:**
- Endpoint returns item-level results for a patient who has completed a baseline.
- Returns 404 or empty list for patients with no completed baseline.
- Therapist cannot access another therapist's patient's baseline items.

---

### 4.5 — Therapist Dashboard Summary Endpoint

**New endpoint:**
- `GET /therapist/dashboard/summary` — returns pre-aggregated dashboard card data

**Context:**  
Currently the dashboard derives counts from `/therapist/dashboard` or `/therapist/patients`. Moving aggregation server-side reduces frontend API composition and N+1 patterns.

**Execution steps:**
1. Read the existing `/therapist/dashboard` handler in `server/app/routers/therapist.py`.
2. Add or extend the endpoint to return:
   ```json
   {
     "total_patients": 12,
     "pending_approvals": 2,
     "patients_without_baseline": 3,
     "patients_without_approved_plan": 4,
     "plans_pending_approval": 1,
     "unread_notification_count": 5
   }
   ```
3. Each count is derived from a single query or small set of queries — no N+1 per patient.
4. If extending the existing endpoint is cleaner than adding a new route, prefer that.

**Validation criteria:**
- All six count fields are returned.
- Counts are accurate for the test data state.
- No N+1 query patterns (use `COUNT` queries, not loading all rows and counting in Python).

---

## Execution Order

All subtasks in Phase 4 are independent. They can be implemented in parallel:

```
4.1, 4.2, 4.3, 4.4, 4.5 — all independent, run in parallel
```

However, for a single developer working sequentially, recommended order:
```
4.3 (simplest — extend existing endpoint)
→ 4.2 (read-only, simple query)
→ 4.1 (three routes, notification model)
→ 4.5 (aggregation query)
→ 4.4 (join-heavy, most complex)
```

## Validation Criteria (Phase Complete)

- [ ] `GET /therapist/notifications` works and returns notification data.
- [ ] `POST /therapist/notifications/{id}/read` marks a notification as read.
- [ ] `GET /plans/{plan_id}/revision-history` returns ordered history entries.
- [ ] `GET /patient/profile` returns therapist name, diagnosis, member_since, best_streak.
- [ ] `GET /baseline/therapist-view/{patient_id}/items` returns item-level baseline detail.
- [ ] `GET /therapist/dashboard` (or `/dashboard/summary`) returns all six count fields.
- [ ] All new endpoints appear in FastAPI `/docs`.
- [ ] All new endpoints enforce role authorization (therapist-only).
- [ ] No breaking changes to existing endpoints.
