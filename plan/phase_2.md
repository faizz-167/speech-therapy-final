# Phase 2 — Schema + Plan Generator Changes

## Objective
Add `initial_level_name` to `PlanTaskAssignment` so every assignment carries the level it was generated at. This column serves as the degradation floor in week-over-week level resolution — a patient can never be pushed below the level they started on for that assignment. Update the plan generator to populate the field at creation time.

## Dependencies
- Phase 1 must be COMPLETED (shared utility must exist before plan_regeneration.py is written in Phase 4, which will also create assignments with this field).
- No dependency on Phases 3–7.

## Subtasks

### 2.1 — Add `initial_level_name` to `PlanTaskAssignment` model
File: `server/app/models/plan.py`

Add one new column to `PlanTaskAssignment`:

```python
initial_level_name: Mapped[str | None] = mapped_column(String, nullable=True)
```

Insert after the existing `clinical_rationale` column (line 41 area). The column is nullable so existing rows without the field do not break.

### 2.2 — Apply the schema change to the running database
**This step must happen before the app boots with the updated model or SQLAlchemy will error.**

This project uses `reset_db.py` as its schema management tool (drops and recreates the entire public schema from ORM models). Choose one of the two paths:

**Path A — Development / fresh environment (destructive, preferred for dev):**
```bash
cd server
python reset_db.py --seed
```
This drops all tables, recreates them from the current ORM models (which now include `initial_level_name`), and re-seeds all clinical data. All existing patient/session data is wiped — only use when that is acceptable.

**Path B — Live environment with existing data (non-destructive):**
Run the following raw SQL against the database before deploying the updated code:
```sql
ALTER TABLE plan_task_assignment
ADD COLUMN IF NOT EXISTS initial_level_name VARCHAR;
```
`IF NOT EXISTS` makes the statement idempotent — safe to re-run. Existing rows will have `NULL` for `initial_level_name`, which is correct: the column is nullable and the week-over-week floor logic in Phase 5 must treat `NULL` as "no floor" (do not degrade below any level).

**Which path to use:** Use Path A in development. Use Path B for any environment where patient data must be preserved. Document which path was used in the status.md notes for this subtask.

### 2.3 — Update `plan_generator.py` to populate `initial_level_name`
File: `server/app/services/plan_generator.py`

In `generate_weekly_plan`, when each `PlanTaskAssignment` is constructed, add:

```python
initial_level_name=baseline_level,
```

This is the `baseline_level` string already resolved earlier in that function (e.g. `"beginner"`, `"intermediate"`, `"advanced"`). Every assignment in the same plan gets the same initial level since the plan is generated at one difficulty tier.

**Note:** Do not change any other logic in `plan_generator.py`.

## Execution Plan

1. Open `server/app/models/plan.py`.
   - Add `initial_level_name: Mapped[str | None] = mapped_column(String, nullable=True)` to `PlanTaskAssignment` after `clinical_rationale`.
2. Apply the schema change to the database (subtask 2.2) — choose Path A or Path B.
3. Open `server/app/services/plan_generator.py`.
   - Read the file fully to locate the `PlanTaskAssignment(...)` constructor call.
   - Add `initial_level_name=baseline_level` as a kwarg.
4. Update `status.md`: mark subtasks 2.1–2.3 as COMPLETED, mark Phase 2 as COMPLETED. Note which migration path was used.

## Validation Criteria
- [ ] `PlanTaskAssignment` model contains `initial_level_name: Mapped[str | None]` column.
- [ ] Column exists in the live database: `SELECT column_name FROM information_schema.columns WHERE table_name='plan_task_assignment' AND column_name='initial_level_name';` returns one row.
- [ ] `plan_generator.py` passes `initial_level_name=baseline_level` when constructing each `PlanTaskAssignment`.
- [ ] No other files changed in this phase.
- [ ] Python import check: `from app.models.plan import PlanTaskAssignment; print(PlanTaskAssignment.initial_level_name)` succeeds without error.
- [ ] Week-over-week floor logic in Phase 5 treats `initial_level_name=NULL` as no floor (no degradation clamping for pre-existing rows).
