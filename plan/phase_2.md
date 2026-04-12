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

### 2.2 — Update `plan_generator.py` to populate `initial_level_name`
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
2. Open `server/app/services/plan_generator.py`.
   - Read the file fully to locate the `PlanTaskAssignment(...)` constructor call.
   - Add `initial_level_name=baseline_level` as a kwarg.
3. Update `status.md`: mark subtasks 2.1–2.2 as COMPLETED, mark Phase 2 as COMPLETED.

## Validation Criteria
- [ ] `PlanTaskAssignment` model contains `initial_level_name: Mapped[str | None]` column.
- [ ] `plan_generator.py` passes `initial_level_name=baseline_level` when constructing each `PlanTaskAssignment`.
- [ ] No other files changed in this phase.
- [ ] Python import check: `from app.models.plan import PlanTaskAssignment; print(PlanTaskAssignment.initial_level_name)` succeeds without error.
