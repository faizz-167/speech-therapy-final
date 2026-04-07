# Backend v2 Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align all backend runtime logic to the v2 database schema — fixing broken old-schema joins, activating unused tables (patient_task_progress, session_emotion_summary, audio_file, therapist_notification, plan_revision_history), and rebuilding the baseline assessment flow with ML-only scoring.

**Architecture:** The Celery scoring worker is the only broken runtime dependency — it still queries removed tables (`prompt_scoring`, `speech_target`). Once fixed, the adaptive progression, emotion summary, and notification systems that already exist in the schema become live. The baseline redesign adds one new ORM model (`BaselineAttempt`) and a new Celery task to complete the ML pipeline without FK conflicts.

**Tech Stack:** FastAPI 0.115, SQLAlchemy 2.0 async, Celery 5.4 + psycopg2 (Celery tasks), Redis pub/sub, Next.js 16 + TypeScript, Tailwind CSS v4.

---

## File Map

### Modified

| File | Changes |
|---|---|
| `server/app/tasks/analysis.py` | Remove old-schema JOINs; read from consolidated `prompt`; load `adaptive_threshold`, `defect_pa_threshold`, `emotion_weights_config`; upsert `patient_task_progress`; upsert `session_emotion_summary`; create `therapist_notification` |
| `server/app/scoring/engine.py` | Add `rule_low_conf_threshold` + `adaptive_stay_max` to `ScoringWeights`; update `weights_from_db_row` |
| `server/app/routers/session.py` | Create `AudioFile` row on every attempt upload |
| `server/app/routers/auth.py` | Create `TherapistNotification` when patient registers |
| `server/app/services/plan_generator.py` | Write `PlanRevisionHistory` row for generate event |
| `server/app/routers/plans.py` | Write `PlanRevisionHistory` for add/move/delete/approve events |
| `server/app/routers/baseline.py` | New ML-based endpoints: start session, per-item upload, complete; filter clinician_rated items |
| `server/app/models/baseline.py` | Add `BaselineAttempt` model |
| `server/app/models/__init__.py` | Export `BaselineAttempt` |
| `server/reset_db.py` | No change — `create_all` picks up new model automatically |
| `client/app/patient/baseline/page.tsx` | Replace self-rating flow with ML audio upload + polling |

### Already correct (no change)

- `server/app/models/operations.py` — `AudioFile`, `TherapistNotification` ORM already correct
- `server/app/models/plan.py` — `PlanRevisionHistory` ORM already correct
- `server/app/models/scoring.py` — `PatientTaskProgress`, `SessionEmotionSummary` ORM already correct
- `server/app/models/content.py` — `AdaptiveThreshold`, `DefectPAThreshold`, `EmotionWeightsConfig` ORM already correct

---

## Task 1: Fix analysis.py — Remove broken old-schema joins

**Files:**
- Modify: `server/app/tasks/analysis.py:204-231`

The current context query joins `prompt_scoring` and `speech_target` — both removed in v2. All their columns now live on `prompt`. This task replaces those joins with direct column reads from `p`.

- [ ] **Step 1: Replace the context SQL query**

Find this block starting at line 204:

```python
        cur.execute(
            "SELECT spa.attempt_id, spa.attempt_number, spa.session_id, spa.prompt_id, spa.audio_file_path,"
            " spa.mic_activated_at, spa.speech_start_at, spa.task_mode, spa.prompt_type,"
            " p.display_content, p.target_response, p.level_id,"
            " ps.target_word_count, ps.target_duration_sec, ps.aq_relevance_threshold,"
            " st.raw_speech_target,"
            " tl.task_id,"
            " s.patient_id, s.plan_id"
            " FROM session_prompt_attempt spa"
            " JOIN session s ON s.session_id = spa.session_id"
            " JOIN prompt p ON p.prompt_id = spa.prompt_id"
            " LEFT JOIN prompt_scoring ps ON ps.prompt_id = spa.prompt_id"
            " LEFT JOIN speech_target st ON st.prompt_id = spa.prompt_id"
            " LEFT JOIN task_level tl ON tl.level_id = p.level_id"
            " WHERE spa.attempt_id = %s",
            (attempt_id,),
        )
```

Replace with:

```python
        cur.execute(
            "SELECT spa.attempt_id, spa.attempt_number, spa.session_id, spa.prompt_id, spa.audio_file_path,"
            " spa.mic_activated_at, spa.speech_start_at, spa.task_mode, spa.prompt_type,"
            " p.display_content, p.target_response, p.level_id,"
            " p.target_word_count, p.target_duration_sec, p.aq_relevance_threshold,"
            " p.speech_target,"
            " tl.task_id,"
            " s.patient_id, s.plan_id"
            " FROM session_prompt_attempt spa"
            " JOIN session s ON s.session_id = spa.session_id"
            " JOIN prompt p ON p.prompt_id = spa.prompt_id"
            " LEFT JOIN task_level tl ON tl.level_id = p.level_id"
            " WHERE spa.attempt_id = %s",
            (attempt_id,),
        )
```

- [ ] **Step 2: Update row unpacking variable name**

Find this destructuring (immediately after the `fetchone()`):

```python
        (
            attempt_id_db, attempt_number, session_id, prompt_id, audio_path,
            mic_at, speech_at, task_mode, prompt_type,
            display_content, target_response, level_id,
            target_word_count, target_duration_sec, aq_threshold,
            raw_speech_target, task_id, patient_id, plan_id,
        ) = row
```

Replace `raw_speech_target` with `speech_target`:

```python
        (
            attempt_id_db, attempt_number, session_id, prompt_id, audio_path,
            mic_at, speech_at, task_mode, prompt_type,
            display_content, target_response, level_id,
            target_word_count, target_duration_sec, aq_threshold,
            speech_target, task_id, patient_id, plan_id,
        ) = row
```

- [ ] **Step 3: Update the target_text fallback reference**

Find:

```python
        target_text = target_response
        if not target_text and raw_speech_target and isinstance(raw_speech_target, dict):
            target_text = raw_speech_target.get("text")
```

Replace:

```python
        target_text = target_response
        if not target_text and speech_target and isinstance(speech_target, dict):
            target_text = speech_target.get("text")
```

- [ ] **Step 4: Verify the file still imports cleanly**

```bash
cd /d/Developer/sppech-therapy-final/server
python -c "from app.tasks.analysis import analyze_attempt; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add server/app/tasks/analysis.py
git commit -m "fix: remove old-schema prompt_scoring and speech_target joins in analysis task"
```

---

## Task 2: Expand ScoringWeights in engine.py

**Files:**
- Modify: `server/app/scoring/engine.py:1-56`

Add `rule_low_conf_threshold` (currently hardcoded as `0.5` in analysis.py) and `adaptive_stay_max` to the dataclass and the builder function.

- [ ] **Step 1: Add two fields to the ScoringWeights dataclass**

Find the `ScoringWeights` dataclass (ends around line 28). Add two fields after `rule_severe_pa_score_cap`:

```python
    rule_severe_pa_score_cap: float = 45.0
    rule_low_conf_threshold: float = 0.50   # Whisper ASR quality gate
    adaptive_stay_max: float = 74.0         # Stay range ceiling (score < this = stay, not advance)
```

- [ ] **Step 2: Update weights_from_db_row to populate new fields**

Find `weights_from_db_row`. After `rule_severe_pa_score_cap=float(row.rule_severe_pa_score_cap),` add:

```python
        rule_low_conf_threshold=float(row.rule_low_conf_threshold) if row.rule_low_conf_threshold is not None else 0.50,
        adaptive_stay_max=float(row.adaptive_stay_max) if row.adaptive_stay_max is not None else 74.0,
```

- [ ] **Step 3: Use rule_low_conf_threshold in analysis.py**

In `analysis.py`, find the line that hardcodes the confidence threshold:

```python
        low_confidence = avg_confidence < 0.5
```

Replace with:

```python
        low_confidence = avg_confidence < weights.rule_low_conf_threshold
```

- [ ] **Step 4: Verify engine imports cleanly**

```bash
cd /d/Developer/sppech-therapy-final/server
python -c "from app.scoring.engine import ScoringWeights, weights_from_db_row, score_attempt; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add server/app/scoring/engine.py server/app/tasks/analysis.py
git commit -m "feat: add rule_low_conf_threshold and adaptive_stay_max to ScoringWeights"
```

---

## Task 3: Load defect_pa_threshold and emotion_weights_config in analysis.py

**Files:**
- Modify: `server/app/tasks/analysis.py`

After the existing task/weights queries (before `conn.close()`), load patient defects, per-defect PA thresholds, and age-group emotion weights. These are used to override the generic severe-PA rule and weight emotion correctly.

- [ ] **Step 1: Add patient + defect queries in the first DB block**

Find the end of the first DB block — after the task WPM query block, just before `conn.close()`. Insert this block:

```python
        # Load patient defect IDs for per-defect PA threshold lookup
        cur.execute(
            "SELECT pre_assigned_defect_ids, date_of_birth FROM patient WHERE patient_id = %s",
            (patient_id,),
        )
        patient_row = cur.fetchone()
        patient_defect_ids: list[str] = []
        patient_dob = None
        if patient_row:
            defect_json, patient_dob = patient_row
            if defect_json and isinstance(defect_json, dict):
                patient_defect_ids = defect_json.get("defect_ids", [])

        # Per-defect PA thresholds — pick the strictest (lowest) min_pa_to_pass
        defect_pa_min: float | None = None
        if patient_defect_ids:
            cur.execute(
                "SELECT min_pa_to_pass FROM defect_pa_threshold WHERE defect_id = ANY(%s)",
                (patient_defect_ids,),
            )
            pa_rows = cur.fetchall()
            if pa_rows:
                defect_pa_min = min(float(r[0]) for r in pa_rows)

        # Emotion weights config by age group
        age_group = "child"
        if patient_dob:
            from datetime import date as _date
            try:
                if hasattr(patient_dob, "year"):
                    dob = patient_dob
                else:
                    dob = _date.fromisoformat(str(patient_dob))
                today = _date.today()
                age_years = (today - dob).days // 365
                age_group = "child" if age_years < 18 else ("senior" if age_years >= 65 else "adult")
            except Exception:
                age_group = "adult"

        cur.execute(
            "SELECT w_happy, w_excited, w_neutral, w_surprised, w_sad, w_angry, w_fearful,"
            " w_positive_affect, w_focused"
            " FROM emotion_weights_config WHERE age_group = %s",
            (age_group,),
        )
        emotion_weights_row = cur.fetchone()

        # Prompt-level adaptive threshold override
        cur.execute(
            "SELECT advance_to_next_level FROM adaptive_threshold WHERE prompt_id = %s",
            (prompt_id,),
        )
        prompt_advance_override = cur.fetchone()
        prompt_advance_threshold: float | None = None
        if prompt_advance_override and prompt_advance_override[0] is not None:
            prompt_advance_threshold = float(prompt_advance_override[0])
```

- [ ] **Step 2: Apply defect_pa_min override in the scoring block**

After `scores = score_attempt(...)` and before the `behavioral_score = ...` extraction, add:

```python
        # Override PA cap threshold with defect-specific threshold if available
        if defect_pa_min is not None and pa < defect_pa_min:
            final_score_override = min(scores["final_score"], weights.rule_severe_pa_score_cap)
            scores = {**scores, "final_score": round(final_score_override, 2)}
            scores["adaptive_decision"] = "drop"
            scores["pass_fail"] = "fail"
            scores["performance_level"] = "needs_improvement"

        # Apply prompt-level advance threshold override
        if prompt_advance_threshold is not None and scores["adaptive_decision"] == "advance":
            if scores["final_score"] < prompt_advance_threshold:
                scores = {**scores, "adaptive_decision": "stay", "pass_fail": "pass", "performance_level": "satisfactory"}
```

- [ ] **Step 3: Verify no import errors**

```bash
cd /d/Developer/sppech-therapy-final/server
python -c "from app.tasks.analysis import analyze_attempt; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add server/app/tasks/analysis.py
git commit -m "feat: load defect_pa_threshold and adaptive_threshold overrides in scoring worker"
```

---

## Task 4: Upsert patient_task_progress in analysis.py

**Files:**
- Modify: `server/app/tasks/analysis.py`

After committing the score detail, upsert `patient_task_progress` to track adaptive state. This is the authoritative source for which level a patient resumes on their next session.

- [ ] **Step 1: Add the upsert helper function at module level**

After the `_SCORE_INSERT_SQL` constant (around line 138), add:

```python
def _upsert_patient_task_progress(
    cur,
    patient_id: str,
    task_id: str,
    current_level_id: str | None,
    adaptive_decision: str,
    final_score: float,
    pass_fail: str,
) -> None:
    """Upsert patient_task_progress for adaptive difficulty tracking."""
    if not task_id:
        return

    # Load all levels for this task ordered by difficulty ascending
    cur.execute(
        "SELECT level_id FROM task_level WHERE task_id = %s ORDER BY difficulty_score ASC",
        (task_id,),
    )
    level_rows = cur.fetchall()
    ordered_levels = [r[0] for r in level_rows]
    if not ordered_levels:
        return

    # Get or create the progress row
    cur.execute(
        "SELECT progress_id, current_level_id, consecutive_passes, consecutive_fails,"
        " overall_accuracy, total_attempts"
        " FROM patient_task_progress"
        " WHERE patient_id = %s AND task_id = %s",
        (patient_id, task_id),
    )
    prog = cur.fetchone()

    is_pass = pass_fail == "pass"
    new_level_id = current_level_id or (ordered_levels[0] if ordered_levels else None)

    if prog:
        progress_id, cur_level, cons_pass, cons_fail, overall_acc, total_att = prog
        # Compute new consecutive counters
        new_cons_pass = (cons_pass or 0) + 1 if is_pass else 0
        new_cons_fail = (cons_fail or 0) + 1 if not is_pass else 0
        new_total = (total_att or 0) + 1
        # Rolling accuracy average
        prev_acc = float(overall_acc) if overall_acc is not None else final_score
        new_acc = round(((prev_acc * (total_att or 0)) + final_score) / new_total, 2)

        # Level advancement
        effective_level = cur_level or new_level_id
        try:
            idx = ordered_levels.index(effective_level)
        except ValueError:
            idx = 0
        if adaptive_decision == "advance":
            idx = min(idx + 1, len(ordered_levels) - 1)
        elif adaptive_decision == "drop":
            idx = max(idx - 1, 0)
        new_level_id = ordered_levels[idx]

        cur.execute(
            "UPDATE patient_task_progress"
            " SET current_level_id=%s, consecutive_passes=%s, consecutive_fails=%s,"
            " overall_accuracy=%s, last_final_score=%s, total_attempts=%s, last_attempted_at=NOW()"
            " WHERE progress_id=%s",
            (new_level_id, new_cons_pass, new_cons_fail, new_acc, round(final_score, 2), new_total, progress_id),
        )
    else:
        import uuid as _uuid
        new_progress_id = str(_uuid.uuid4())
        new_cons_pass = 1 if is_pass else 0
        new_cons_fail = 0 if is_pass else 1
        cur.execute(
            "INSERT INTO patient_task_progress"
            " (progress_id, patient_id, task_id, current_level_id, consecutive_passes, consecutive_fails,"
            " overall_accuracy, last_final_score, total_attempts, last_attempted_at)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1,NOW())",
            (new_progress_id, patient_id, task_id, new_level_id,
             new_cons_pass, new_cons_fail, round(final_score, 2), round(final_score, 2)),
        )
```

- [ ] **Step 2: Call the helper after the score detail insert in the second DB block**

Find the second `conn.commit()` (around line 365, after the score detail insert and attempt update). Just before `conn.commit()`, add:

```python
        _upsert_patient_task_progress(
            cur, str(patient_id), task_id,
            level_id, adaptive_decision, final_score, pass_fail,
        )
```

- [ ] **Step 3: Add the same call in the no-speech branch**

Find the no-speech early-return block (around line 277). Just before `conn.commit()` in that block, add:

```python
            _upsert_patient_task_progress(
                cur, str(patient_id), task_id,
                level_id, "drop", 0.0, "fail",
            )
```

- [ ] **Step 4: Verify**

```bash
cd /d/Developer/sppech-therapy-final/server
python -c "from app.tasks.analysis import analyze_attempt, _upsert_patient_task_progress; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add server/app/tasks/analysis.py
git commit -m "feat: upsert patient_task_progress on every scored attempt"
```

---

## Task 5: Upsert session_emotion_summary in analysis.py

**Files:**
- Modify: `server/app/tasks/analysis.py`

After each scored attempt, recalculate and upsert the per-session emotion summary. This gives the progress dashboard a stable aggregated view of emotion trends per session.

- [ ] **Step 1: Add the upsert helper at module level**

After `_upsert_patient_task_progress` function, add:

```python
def _upsert_session_emotion_summary(cur, session_id: str, patient_id: str) -> None:
    """Recalculate and upsert session_emotion_summary from all scored attempts in session."""
    cur.execute(
        "SELECT asd.dominant_emotion, asd.engagement_score, asd.pass_fail"
        " FROM attempt_score_detail asd"
        " JOIN session_prompt_attempt spa ON spa.attempt_id = asd.attempt_id"
        " WHERE spa.session_id = %s",
        (session_id,),
    )
    rows = cur.fetchall()
    if not rows:
        return

    emotions = [r[0] for r in rows if r[0]]
    engagement_scores = [float(r[1]) for r in rows if r[1] is not None]
    drop_count = sum(1 for r in rows if r[2] == "fail")

    from collections import Counter
    dominant = Counter(emotions).most_common(1)[0][0] if emotions else "neutral"
    avg_eng = round(sum(engagement_scores) / len(engagement_scores), 2) if engagement_scores else 0.0
    # avg_frustration: average engagement of attempts where emotion is angry or fearful
    frustration_scores = [float(r[1]) for r in rows if r[0] in ("angry", "fearful") and r[1] is not None]
    avg_frustration = round(sum(frustration_scores) / len(frustration_scores), 2) if frustration_scores else 0.0

    # Check if summary exists
    cur.execute(
        "SELECT summary_id FROM session_emotion_summary WHERE session_id = %s",
        (session_id,),
    )
    existing = cur.fetchone()
    if existing:
        cur.execute(
            "UPDATE session_emotion_summary"
            " SET dominant_emotion=%s, avg_frustration=%s, avg_engagement=%s, drop_count=%s"
            " WHERE session_id=%s",
            (dominant, avg_frustration, avg_eng, drop_count, session_id),
        )
    else:
        import uuid as _uuid
        from datetime import date as _date
        cur.execute(
            "INSERT INTO session_emotion_summary"
            " (summary_id, session_id, patient_id, session_date, dominant_emotion,"
            " avg_frustration, avg_engagement, drop_count)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (str(_uuid.uuid4()), session_id, patient_id, _date.today().isoformat(),
             dominant, avg_frustration, avg_eng, drop_count),
        )
```

- [ ] **Step 2: Call the helper after patient_task_progress upsert (in both branches)**

In the normal scoring second DB block (just before `conn.commit()`), add after the `_upsert_patient_task_progress(...)` call:

```python
        _upsert_session_emotion_summary(cur, str(session_id), str(patient_id))
```

In the no-speech branch, add after its `_upsert_patient_task_progress(...)` call:

```python
            _upsert_session_emotion_summary(cur, str(session_id), str(patient_id))
```

- [ ] **Step 3: Commit**

```bash
git add server/app/tasks/analysis.py
git commit -m "feat: upsert session_emotion_summary on every scored attempt"
```

---

## Task 6: Create therapist_notification in analysis.py and auth.py

**Files:**
- Modify: `server/app/tasks/analysis.py`
- Modify: `server/app/routers/auth.py`

Two notification triggers: (1) when Celery flags an attempt for review, (2) when a patient registers.

- [ ] **Step 1: Add notification helper in analysis.py**

After `_upsert_session_emotion_summary`, add:

```python
def _create_review_notification(cur, therapist_id: str, patient_id: str, attempt_id: str) -> None:
    """Create a therapist_notification row when an attempt needs manual review."""
    import uuid as _uuid
    cur.execute(
        "INSERT INTO therapist_notification"
        " (notification_id, therapist_id, type, patient_id, attempt_id, message, is_read, created_at)"
        " VALUES (%s,%s,%s,%s,%s,%s,false,NOW())",
        (
            str(_uuid.uuid4()),
            therapist_id,
            "review_flagged",
            patient_id,
            attempt_id,
            "An attempt has been flagged for review due to low ASR confidence.",
        ),
    )
```

- [ ] **Step 2: Load therapist_id in the first DB block**

In the first DB block of `analyze_attempt`, after the session query at the top, find where `patient_id` and `plan_id` are extracted. Add a query for the therapist:

```python
        cur.execute(
            "SELECT assigned_therapist_id FROM patient WHERE patient_id = %s",
            (patient_id,),
        )
        therapist_row = cur.fetchone()
        assigned_therapist_id = str(therapist_row[0]) if therapist_row and therapist_row[0] else None
```

- [ ] **Step 3: Call notification helper in the second DB block**

After `_upsert_session_emotion_summary(...)` and before `conn.commit()`, add:

```python
        if review_recommended and assigned_therapist_id:
            _create_review_notification(cur, assigned_therapist_id, str(patient_id), str(attempt_id))
```

- [ ] **Step 4: Create notification on patient register in auth.py**

In `server/app/routers/auth.py`, add import at top:

```python
from app.models.operations import TherapistNotification
```

In `register_patient`, after `await db.commit()` and before `await db.refresh(patient)`, add:

```python
    notification = TherapistNotification(
        therapist_id=therapist.therapist_id,
        type="patient_registered",
        patient_id=patient.patient_id,
        message=f"New patient {patient.full_name} registered and is awaiting your approval.",
    )
    db.add(notification)
    await db.commit()
```

- [ ] **Step 5: Verify both files**

```bash
cd /d/Developer/sppech-therapy-final/server
python -c "from app.tasks.analysis import analyze_attempt; print('OK')"
python -c "from app.routers.auth import router; print('OK')"
```

Expected: both print `OK`

- [ ] **Step 6: Commit**

```bash
git add server/app/tasks/analysis.py server/app/routers/auth.py
git commit -m "feat: create therapist_notification on review_recommended and patient_registered events"
```

---

## Task 7: Create AudioFile row on session upload

**Files:**
- Modify: `server/app/routers/session.py`

When a patient uploads audio for an attempt, create a matching `AudioFile` row. This enables future audio cleanup and session replay.

- [ ] **Step 1: Add AudioFile import**

In `server/app/routers/session.py` top imports, add:

```python
from app.models.operations import AudioFile
```

- [ ] **Step 2: Create AudioFile after saving the physical file**

In `submit_attempt`, after `await f.write(content)` (the file save), and before `attempt = SessionPromptAttempt(...)`, add:

```python
    file_size = len(content)
    ext_mime = "audio/webm" if ext == ".webm" else "audio/wav"
```

After `db.add(attempt)` and `await db.commit()`, add:

```python
    audio_file = AudioFile(
        patient_id=patient.patient_id,
        session_id=session.session_id,
        attempt_id=attempt.attempt_id,
        file_path=filepath,
        file_size_bytes=file_size,
        mime_type=ext_mime,
    )
    db.add(audio_file)
    await db.commit()
```

- [ ] **Step 3: Verify**

```bash
cd /d/Developer/sppech-therapy-final/server
python -c "from app.routers.session import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add server/app/routers/session.py
git commit -m "feat: create audio_file row on every session attempt upload"
```

---

## Task 8: Add PlanRevisionHistory to plan generator and plans router

**Files:**
- Modify: `server/app/services/plan_generator.py`
- Modify: `server/app/routers/plans.py`

Write `PlanRevisionHistory` rows for generate, add, move, delete, and approve events. This gives the therapist an audit trail visible in the Kanban editor.

- [ ] **Step 1: Import PlanRevisionHistory in plan_generator.py**

At the top of `server/app/services/plan_generator.py`, add:

```python
from app.models.plan import TherapyPlan, PlanTaskAssignment, PlanRevisionHistory
```

(Replace the existing `from app.models.plan import TherapyPlan, PlanTaskAssignment`)

- [ ] **Step 2: Write "generate" history row in generate_weekly_plan**

In `generate_weekly_plan`, just before `await db.commit()` at the end, add:

```python
    revision = PlanRevisionHistory(
        plan_id=plan.plan_id,
        therapist_id=therapist.therapist_id,
        action="generate",
        new_value={"task_count": len(tasks[:14]), "baseline_level": baseline_level},
        note=f"Plan auto-generated at {baseline_level} level for {len(defect_ids)} defect(s).",
    )
    db.add(revision)
```

- [ ] **Step 3: Import PlanRevisionHistory in plans.py router**

Add to the existing imports in `server/app/routers/plans.py`:

```python
from app.models.plan import TherapyPlan, PlanTaskAssignment, PlanRevisionHistory
```

- [ ] **Step 4: Read plans.py to find add/delete/update/approve handlers**

```bash
cat -n /d/Developer/sppech-therapy-final/server/app/routers/plans.py | head -200
```

- [ ] **Step 5: Add history row to the approve endpoint**

Find the approve endpoint (it sets `plan.status = "approved"`). After `await db.commit()`, add:

```python
    revision = PlanRevisionHistory(
        plan_id=plan.plan_id,
        therapist_id=therapist.therapist_id,
        action="approve",
        note="Plan approved by therapist.",
    )
    db.add(revision)
    await db.commit()
```

- [ ] **Step 6: Add history row to add-task endpoint**

Find the endpoint that adds a new assignment to a plan. After `db.add(assignment)` and `await db.commit()`, add:

```python
    revision = PlanRevisionHistory(
        plan_id=plan.plan_id,
        therapist_id=therapist.therapist_id,
        action="add_task",
        assignment_id=assignment.assignment_id,
        new_value={"task_id": assignment.task_id, "day_index": assignment.day_index},
    )
    db.add(revision)
    await db.commit()
```

- [ ] **Step 7: Add history row to delete-assignment endpoint**

Find the endpoint that deletes an assignment. Before `await db.delete(assignment)`, capture the old state and add:

```python
    old_val = {"task_id": assignment.task_id, "day_index": assignment.day_index}
```

After `await db.commit()`, add:

```python
    revision = PlanRevisionHistory(
        plan_id=plan.plan_id,
        therapist_id=therapist.therapist_id,
        action="remove_task",
        old_value=old_val,
    )
    db.add(revision)
    await db.commit()
```

- [ ] **Step 8: Add history row to move/update-assignment endpoint**

Find the endpoint that updates day_index or priority_order. After `await db.commit()`, add:

```python
    revision = PlanRevisionHistory(
        plan_id=plan.plan_id,
        therapist_id=therapist.therapist_id,
        action="reorder",
        assignment_id=assignment.assignment_id,
        new_value={"day_index": assignment.day_index, "priority_order": assignment.priority_order},
    )
    db.add(revision)
    await db.commit()
```

- [ ] **Step 9: Verify**

```bash
cd /d/Developer/sppech-therapy-final/server
python -c "from app.services.plan_generator import generate_weekly_plan; print('OK')"
python -c "from app.routers.plans import router; print('OK')"
```

Expected: both `OK`

- [ ] **Step 10: Commit**

```bash
git add server/app/services/plan_generator.py server/app/routers/plans.py
git commit -m "feat: write plan_revision_history for generate, approve, add, remove, reorder events"
```

---

## Task 9: Add BaselineAttempt model and analyze_baseline_attempt Celery task

**Files:**
- Modify: `server/app/models/baseline.py`
- Modify: `server/app/models/__init__.py`
- Create: `server/app/tasks/baseline_analysis.py`

The `session_prompt_attempt` table has a NOT NULL FK to `prompt`. Baseline items are in `baseline_item` — a different table. To avoid FK violations, add a lightweight `baseline_attempt` table that tracks one audio upload per baseline item per session.

- [ ] **Step 1: Add BaselineAttempt model to baseline.py**

Open `server/app/models/baseline.py`. At the bottom, after the `BaselineItemResult` class, add:

```python
class BaselineAttempt(Base):
    """Tracks one audio recording attempt for a single baseline_item within a baseline session."""
    __tablename__ = "baseline_attempt"

    attempt_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("session.session_id"))
    item_id: Mapped[str] = mapped_column(String, ForeignKey("baseline_item.item_id"))
    audio_file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    result: Mapped[str] = mapped_column(String, default="pending")  # pending | scored | failed
    ml_phoneme_accuracy: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    ml_word_accuracy: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    ml_fluency_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    ml_speech_rate_wpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ml_confidence: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    asr_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    computed_score: Mapped[float | None] = mapped_column(Numeric, nullable=True)  # formula_mode applied
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc))
```

Also add the needed imports at the top of `baseline.py` (they are already present: `Integer`, `Numeric`, `Text`, `String`, `ForeignKey`, `TIMESTAMP`, `uuid`, `datetime`). Confirm the file has `from sqlalchemy.dialects.postgresql import UUID`.

- [ ] **Step 2: Export BaselineAttempt in __init__.py**

Open `server/app/models/__init__.py`. Find the baseline imports line and add `BaselineAttempt`:

```python
from app.models.baseline import (
    BaselineAssessment, BaselineDefectMapping, BaselineSection,
    BaselineItem, PatientBaselineResult, BaselineItemResult, BaselineAttempt,
)
```

- [ ] **Step 3: Create baseline_analysis.py Celery task**

Create `server/app/tasks/baseline_analysis.py`:

```python
"""Celery task: score a single baseline audio attempt using the ML pipeline."""
import os
import uuid
from numbers import Number

import psycopg2

from app.celery_app import celery_app
from app.config import settings


def _get_conn():
    return psycopg2.connect(settings.database_url_sync)


def _as_float(value, default: float = 0.0) -> float:
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _baseline_score(formula_mode: str, pa: float, wa: float, fs: float,
                    wpm: float, formula_weights: dict | None, wpm_range: dict | None) -> float:
    """Compute a 0–100 baseline score according to formula_mode."""
    if formula_mode == "auto_phoneme_only":
        # Phoneme accuracy drives the score; word accuracy is secondary
        fw = formula_weights or {"pa": 0.80, "wa": 0.20}
        score = pa * fw.get("pa", 0.80) + wa * fw.get("wa", 0.20)
    elif formula_mode == "auto_simple":
        fw = formula_weights or {"pa": 0.50, "wa": 0.30, "fs": 0.20}
        score = pa * fw.get("pa", 0.50) + wa * fw.get("wa", 0.30) + fs * fw.get("fs", 0.20)
        # Apply WPM penalty when wpm_range is configured and WPM is out of range
        if wpm_range:
            ideal_min = wpm_range.get("min", 0)
            ideal_max = wpm_range.get("max", 999)
            if wpm > 0 and not (ideal_min <= wpm <= ideal_max):
                score = max(0.0, score - 10.0)
    else:
        # Fallback for unknown modes: average PA and WA
        score = (pa + wa) / 2.0
    return round(min(100.0, max(0.0, score)), 2)


@celery_app.task(name="app.tasks.baseline_analysis.analyze_baseline_attempt", bind=True, max_retries=2)
def analyze_baseline_attempt(self, attempt_id: str):
    """Score a baseline audio attempt and update the baseline_attempt row."""
    from app.ml.whisper_asr import transcribe
    from app.ml.hubert_phoneme import align_phonemes
    from app.ml.spacy_disfluency import score_disfluency

    conn = None
    try:
        conn = _get_conn()
        cur = conn.cursor()

        cur.execute(
            "SELECT ba.attempt_id, ba.audio_file_path, ba.item_id,"
            " bi.formula_mode, bi.formula_weights, bi.wpm_range, bi.expected_output"
            " FROM baseline_attempt ba"
            " JOIN baseline_item bi ON bi.item_id = ba.item_id"
            " WHERE ba.attempt_id = %s",
            (attempt_id,),
        )
        row = cur.fetchone()
        if not row:
            return

        attempt_id_db, audio_path, item_id, formula_mode, formula_weights, wpm_range, expected_output = row

        if not audio_path or not os.path.exists(audio_path):
            cur.execute(
                "UPDATE baseline_attempt SET result='failed' WHERE attempt_id=%s",
                (attempt_id,),
            )
            conn.commit()
            return

        conn.close()
        conn = None

        asr = transcribe(audio_path, expected_text=expected_output)
        transcript = asr["transcript"]
        duration = _as_float(asr["duration"])
        avg_confidence = _as_float(asr["avg_confidence"])

        phoneme_result = align_phonemes(audio_path, transcript)
        disfluency_result = score_disfluency(transcript, duration)

        pa = _as_float(phoneme_result["phoneme_accuracy"], 70.0)
        fs = _as_float(disfluency_result["fluency_score"], 50.0)
        wpm = _as_float((len(transcript.split()) / duration * 60) if duration > 0 else 0)

        # Word accuracy against expected output
        wa = 75.0
        if expected_output and transcript:
            target_words = {w.strip(".,!?;:").lower() for w in expected_output.split()}
            spoken_words = {w.strip(".,!?;:").lower() for w in transcript.split()}
            if target_words:
                wa = round(len(target_words & spoken_words) / len(target_words) * 100, 2)

        computed = _baseline_score(formula_mode or "auto_simple", pa, wa, fs, wpm, formula_weights, wpm_range)
        wpm_int = int(round(wpm))

        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE baseline_attempt"
            " SET result='scored', ml_phoneme_accuracy=%s, ml_word_accuracy=%s,"
            " ml_fluency_score=%s, ml_speech_rate_wpm=%s, ml_confidence=%s,"
            " asr_transcript=%s, computed_score=%s"
            " WHERE attempt_id=%s",
            (pa, wa, fs, wpm_int, round(avg_confidence * 100, 2),
             transcript, computed, attempt_id),
        )
        conn.commit()

    except Exception as exc:
        try:
            if conn is not None and not conn.closed:
                conn.rollback()
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=5)
    finally:
        if conn is not None and not conn.closed:
            conn.close()
```

- [ ] **Step 4: Verify model and task import cleanly**

```bash
cd /d/Developer/sppech-therapy-final/server
python -c "from app.models.baseline import BaselineAttempt; print('OK')"
python -c "from app.tasks.baseline_analysis import analyze_baseline_attempt; print('OK')"
```

Expected: both `OK`

- [ ] **Step 5: Commit**

```bash
git add server/app/models/baseline.py server/app/models/__init__.py server/app/tasks/baseline_analysis.py
git commit -m "feat: add BaselineAttempt model and analyze_baseline_attempt Celery task"
```

---

## Task 10: Redesign baseline router

**Files:**
- Modify: `server/app/routers/baseline.py`

Replace the self-rating baseline flow with ML-based endpoints:
- `GET /baseline/exercises` — filters `clinician_rated` items; returns real assessment/section/item hierarchy
- `POST /baseline/start` — creates a `Session` row with `session_type="baseline"`
- `POST /baseline/{session_id}/attempt` — saves audio, queues `analyze_baseline_attempt`
- `GET /baseline/attempt/{attempt_id}` — polls ML result
- `POST /baseline/{session_id}/complete` — aggregates ML scores into `baseline_item_result` + `patient_baseline_result`

Keep `GET /baseline/result` and `GET /baseline/therapist-view/{patient_id}` unchanged.

- [ ] **Step 1: Add new imports to baseline.py**

Replace the current import block at the top with:

```python
import os
import uuid
import aiofiles
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.auth import require_patient, require_therapist
from app.config import settings
from app.models.users import Patient, Therapist
from app.models.content import Defect
from app.models.scoring import Session
from app.models.baseline import (
    BaselineAssessment, BaselineDefectMapping, BaselineSection,
    BaselineItem, PatientBaselineResult, BaselineItemResult, BaselineAttempt,
)
from app.schemas.baseline import (
    BaselineAssessmentOut, BaselineSectionOut, BaselineItemOut,
    BaselineResultOut,
)
from app.tasks.baseline_analysis import analyze_baseline_attempt
```

- [ ] **Step 2: Rewrite GET /baseline/exercises to filter clinician_rated**

Replace the entire `get_baseline_exercises` function with:

```python
BASELINE_ITEM_CAP = 7
EXCLUDED_FORMULA_MODES = {"clinician_rated"}


@router.get("/exercises", response_model=list[BaselineAssessmentOut])
async def get_baseline_exercises(
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    if not patient.pre_assigned_defect_ids:
        raise HTTPException(400, "No defects assigned to patient")
    defect_ids = patient.pre_assigned_defect_ids.get("defect_ids", [])

    mapping_result = await db.execute(
        select(BaselineDefectMapping)
        .where(BaselineDefectMapping.defect_id.in_(defect_ids))
    )
    baseline_ids = list({m.baseline_id for m in mapping_result.scalars().all()})
    if not baseline_ids:
        raise HTTPException(404, "No baseline assessments found for assigned defects")

    assessments_result = await db.execute(
        select(BaselineAssessment).where(BaselineAssessment.baseline_id.in_(baseline_ids))
    )
    assessments = assessments_result.scalars().all()

    out: list[BaselineAssessmentOut] = []
    total_items = 0
    for assessment in assessments:
        if total_items >= BASELINE_ITEM_CAP:
            break
        sections_result = await db.execute(
            select(BaselineSection)
            .where(BaselineSection.baseline_id == assessment.baseline_id)
            .order_by(BaselineSection.order_index)
        )
        sections_out: list[BaselineSectionOut] = []
        for section in sections_result.scalars().all():
            if total_items >= BASELINE_ITEM_CAP:
                break
            items_result = await db.execute(
                select(BaselineItem)
                .where(
                    BaselineItem.section_id == section.section_id,
                    BaselineItem.formula_mode.notin_(EXCLUDED_FORMULA_MODES)
                    | BaselineItem.formula_mode.is_(None),
                )
                .order_by(BaselineItem.order_index)
            )
            items = items_result.scalars().all()
            remaining = BASELINE_ITEM_CAP - total_items
            items = items[:remaining]
            if not items:
                continue
            sections_out.append(BaselineSectionOut(
                section_id=section.section_id,
                section_name=section.section_name,
                instructions=section.instructions,
                order_index=section.order_index,
                items=[BaselineItemOut(
                    item_id=i.item_id,
                    task_name=i.task_name,
                    instruction=i.instruction,
                    display_content=i.display_content,
                    expected_output=i.expected_output,
                    response_type=i.response_type,
                    target_phoneme=i.target_phoneme,
                    formula_weights=i.formula_weights,
                    fusion_weights=i.fusion_weights,
                    wpm_range=i.wpm_range,
                ) for i in items],
            ))
            total_items += len(items)
        if sections_out:
            out.append(BaselineAssessmentOut(
                baseline_id=assessment.baseline_id,
                name=assessment.name,
                domain=assessment.domain,
                sections=sections_out,
            ))
    return out
```

- [ ] **Step 3: Add POST /baseline/start**

After `get_baseline_exercises`, add:

```python
@router.post("/start")
async def start_baseline_session(
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    """Create a baseline session. Returns session_id used for all subsequent baseline attempts."""
    session = Session(
        session_id=uuid.uuid4(),
        patient_id=patient.patient_id,
        therapist_id=patient.assigned_therapist_id,
        session_type="baseline",
    )
    db.add(session)
    await db.commit()
    return {"session_id": str(session.session_id)}
```

- [ ] **Step 4: Add POST /baseline/{session_id}/attempt**

```python
@router.post("/{session_id}/attempt")
async def submit_baseline_attempt(
    session_id: str,
    item_id: str = Form(...),
    audio: UploadFile = File(...),
    patient: Annotated[Patient, Depends(require_patient)] = None,
    db: AsyncSession = Depends(get_db),
):
    """Upload audio for one baseline item. Queues ML scoring asynchronously."""
    session = await db.get(Session, session_id)
    if not session or session.patient_id != patient.patient_id or session.session_type != "baseline":
        raise HTTPException(404, "Baseline session not found")

    item = await db.get(BaselineItem, item_id)
    if not item:
        raise HTTPException(404, "Baseline item not found")

    ext = os.path.splitext(audio.filename or "audio.webm")[1] or ".webm"
    filename = f"baseline_{uuid.uuid4()}{ext}"
    filepath = os.path.join(settings.upload_dir, filename)
    os.makedirs(settings.upload_dir, exist_ok=True)
    async with aiofiles.open(filepath, "wb") as f:
        content = await audio.read()
        await f.write(content)

    attempt = BaselineAttempt(
        session_id=uuid.UUID(session_id),
        item_id=item_id,
        audio_file_path=filepath,
        result="pending",
    )
    db.add(attempt)
    await db.commit()

    analyze_baseline_attempt.delay(str(attempt.attempt_id))

    return {"attempt_id": str(attempt.attempt_id), "result": "pending"}
```

- [ ] **Step 5: Add GET /baseline/attempt/{attempt_id} polling endpoint**

```python
@router.get("/attempt/{attempt_id}")
async def poll_baseline_attempt(
    attempt_id: str,
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    """Poll the ML scoring result for a single baseline item attempt."""
    result = await db.execute(
        select(BaselineAttempt)
        .join(Session, BaselineAttempt.session_id == Session.session_id)
        .where(
            BaselineAttempt.attempt_id == attempt_id,
            Session.patient_id == patient.patient_id,
        )
    )
    attempt = result.scalar_one_or_none()
    if not attempt:
        raise HTTPException(404, "Baseline attempt not found")
    return {
        "attempt_id": attempt_id,
        "result": attempt.result,
        "computed_score": float(attempt.computed_score) if attempt.computed_score is not None else None,
        "phoneme_accuracy": float(attempt.ml_phoneme_accuracy) if attempt.ml_phoneme_accuracy is not None else None,
        "asr_transcript": attempt.asr_transcript,
    }
```

- [ ] **Step 6: Add POST /baseline/{session_id}/complete**

```python
@router.post("/{session_id}/complete", response_model=BaselineResultOut)
async def complete_baseline_session(
    session_id: str,
    patient: Annotated[Patient, Depends(require_patient)],
    db: AsyncSession = Depends(get_db),
):
    """Aggregate all scored baseline attempts into patient_baseline_result and baseline_item_result rows."""
    session = await db.get(Session, session_id)
    if not session or session.patient_id != patient.patient_id or session.session_type != "baseline":
        raise HTTPException(404, "Baseline session not found")

    attempts_result = await db.execute(
        select(BaselineAttempt).where(
            BaselineAttempt.session_id == uuid.UUID(session_id),
            BaselineAttempt.result == "scored",
        )
    )
    scored_attempts = attempts_result.scalars().all()
    if not scored_attempts:
        raise HTTPException(400, "No scored baseline attempts found. Ensure all items have been uploaded and scored.")

    # Resolve which baseline_assessment these items belong to
    item_ids = [a.item_id for a in scored_attempts]
    items_result = await db.execute(
        select(BaselineItem).where(BaselineItem.item_id.in_(item_ids))
    )
    items_by_id = {i.item_id: i for i in items_result.scalars().all()}

    # Find baseline_id via section
    section_ids = list({i.section_id for i in items_by_id.values()})
    sections_result = await db.execute(
        select(BaselineSection).where(BaselineSection.section_id.in_(section_ids))
    )
    baseline_ids = list({s.baseline_id for s in sections_result.scalars().all()})
    primary_baseline_id = baseline_ids[0] if baseline_ids else "unknown"

    avg_score = sum(
        float(a.computed_score) for a in scored_attempts if a.computed_score is not None
    ) / len(scored_attempts)
    raw_score = int(round(avg_score))
    severity = "advanced" if avg_score >= 80 else ("medium" if avg_score >= 70 else "easy")

    result_id = uuid.uuid4()
    baseline_result = PatientBaselineResult(
        result_id=result_id,
        patient_id=patient.patient_id,
        baseline_id=primary_baseline_id,
        therapist_id=patient.assigned_therapist_id,
        assessed_on=date.today(),
        raw_score=raw_score,
        severity_rating=severity,
    )
    db.add(baseline_result)
    await db.flush()

    for attempt in scored_attempts:
        db.add(BaselineItemResult(
            item_result_id=uuid.uuid4(),
            result_id=result_id,
            item_id=attempt.item_id,
            score_given=int(round(float(attempt.computed_score or 0))),
        ))

    await db.commit()
    assessment = await db.get(BaselineAssessment, primary_baseline_id)
    return BaselineResultOut(
        result_id=str(result_id),
        baseline_name=assessment.name if assessment else primary_baseline_id,
        raw_score=raw_score,
        level=severity,
        assessed_on=date.today().isoformat(),
    )
```

- [ ] **Step 7: Remove the old POST /baseline/submit endpoint**

Delete the entire `submit_baseline` function (it accepts self-ratings — replaced by the new flow above).

- [ ] **Step 8: Verify the router imports cleanly**

```bash
cd /d/Developer/sppech-therapy-final/server
python -c "from app.routers.baseline import router; print('OK')"
```

Expected: `OK`

- [ ] **Step 9: Commit**

```bash
git add server/app/routers/baseline.py
git commit -m "feat: redesign baseline router with ML-based audio upload and scoring flow"
```

---

## Task 11: Update baseline frontend page

**Files:**
- Modify: `client/app/patient/baseline/page.tsx`

Replace the self-rating UI (1–5 star/slider rating per item) with a recording-upload-wait flow that mirrors the therapy exercise page. The patient records audio → it uploads → the UI polls until the ML score arrives → then moves to the next item → at the end calls `/baseline/{session_id}/complete`.

- [ ] **Step 1: Read the full current page**

```bash
cat -n /d/Developer/sppech-therapy-final/client/app/patient/baseline/page.tsx
```

- [ ] **Step 2: Rewrite BaselinePage with the new flow**

Replace the full file with:

```tsx
"use client";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { NeoCard } from "@/components/ui/NeoCard";
import { NeoButton } from "@/components/ui/NeoButton";
import { SkeletonList, ErrorBanner } from "@/components/ui/Skeletons";

interface BaselineItem {
  item_id: string;
  task_name: string | null;
  instruction: string | null;
  display_content: string | null;
  expected_output: string | null;
  response_type: string | null;
}
interface BaselineSection {
  section_id: string;
  section_name: string;
  instructions: string | null;
  items: BaselineItem[];
}
interface BaselineAssessment {
  baseline_id: string;
  name: string;
  domain: string;
  sections: BaselineSection[];
}
interface AttemptResult {
  attempt_id: string;
  result: string;
  computed_score: number | null;
  phoneme_accuracy: number | null;
  asr_transcript: string | null;
}

type Phase = "idle" | "recording" | "uploading" | "scoring" | "done_item";

export default function BaselinePage() {
  const [assessments, setAssessments] = useState<BaselineAssessment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [itemIdx, setItemIdx] = useState(0);
  const [phase, setPhase] = useState<Phase>("idle");
  const [itemScore, setItemScore] = useState<AttemptResult | null>(null);
  const [completed, setCompleted] = useState(false);
  const [finalLevel, setFinalLevel] = useState<string | null>(null);

  const mediaRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  // Flatten all items across all assessments/sections
  const allItems: BaselineItem[] = assessments.flatMap(a =>
    a.sections.flatMap(s => s.items)
  );
  const currentItem = allItems[itemIdx] ?? null;

  useEffect(() => {
    (async () => {
      try {
        const data = await api.get<BaselineAssessment[]>("/baseline/exercises");
        setAssessments(data);
        const sess = await api.post<{ session_id: string }>("/baseline/start", {});
        setSessionId(sess.session_id);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load baseline");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data); };
      recorder.start();
      mediaRef.current = recorder;
      setPhase("recording");
    } catch {
      setError("Microphone permission denied");
    }
  };

  const stopAndUpload = async () => {
    if (!mediaRef.current || !sessionId || !currentItem) return;
    setPhase("uploading");
    mediaRef.current.stop();
    mediaRef.current.stream.getTracks().forEach(t => t.stop());

    await new Promise<void>(res => {
      if (mediaRef.current) mediaRef.current.onstop = () => res();
    });

    const blob = new Blob(chunksRef.current, { type: "audio/webm" });
    const form = new FormData();
    form.append("item_id", currentItem.item_id);
    form.append("audio", blob, "recording.webm");

    try {
      const upload = await api.upload<{ attempt_id: string; result: string }>(
        `/baseline/${sessionId}/attempt`, form
      );
      setPhase("scoring");
      await pollUntilScored(upload.attempt_id);
    } catch {
      setError("Upload failed. Please try again.");
      setPhase("idle");
    }
  };

  const pollUntilScored = async (attemptId: string) => {
    for (let i = 0; i < 60; i++) {
      await new Promise(res => setTimeout(res, 2000));
      try {
        const result = await api.get<AttemptResult>(`/baseline/attempt/${attemptId}`);
        if (result.result === "scored") {
          setItemScore(result);
          setPhase("done_item");
          return;
        }
        if (result.result === "failed") {
          setError("Scoring failed for this item. Moving to next.");
          setPhase("done_item");
          setItemScore(null);
          return;
        }
      } catch {
        // Keep polling
      }
    }
    setError("Scoring timed out. Moving to next item.");
    setPhase("done_item");
  };

  const nextItem = () => {
    setItemScore(null);
    setPhase("idle");
    if (itemIdx + 1 >= allItems.length) {
      completeBaseline();
    } else {
      setItemIdx(idx => idx + 1);
    }
  };

  const completeBaseline = async () => {
    if (!sessionId) return;
    try {
      const result = await api.post<{ level: string; raw_score: number }>(
        `/baseline/${sessionId}/complete`, {}
      );
      setFinalLevel(result.level);
      setCompleted(true);
    } catch {
      setError("Failed to complete baseline. Please contact your therapist.");
    }
  };

  if (loading) return <SkeletonList />;
  if (error) return <ErrorBanner message={error} />;

  if (completed) {
    return (
      <div className="max-w-lg mx-auto mt-16 text-center">
        <NeoCard>
          <h2 className="text-2xl font-bold mb-2">Baseline Complete!</h2>
          <p className="text-gray-600 mb-4">
            Your starting level is <span className="font-semibold capitalize">{finalLevel}</span>.
          </p>
          <p className="text-sm text-gray-500">Your therapist will review your results and approve your therapy plan.</p>
        </NeoCard>
      </div>
    );
  }

  if (!currentItem) {
    return <ErrorBanner message="No baseline items available. Contact your therapist." />;
  }

  return (
    <div className="max-w-xl mx-auto mt-8 space-y-4 px-4">
      <div className="flex justify-between text-sm text-gray-500">
        <span>Item {itemIdx + 1} of {allItems.length}</span>
        <span>{Math.round(((itemIdx) / allItems.length) * 100)}% complete</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2">
        <div
          className="bg-blue-500 h-2 rounded-full transition-all"
          style={{ width: `${(itemIdx / allItems.length) * 100}%` }}
        />
      </div>

      <NeoCard>
        {currentItem.task_name && (
          <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">{currentItem.task_name}</p>
        )}
        {currentItem.instruction && (
          <p className="text-sm text-gray-600 mb-3">{currentItem.instruction}</p>
        )}
        {currentItem.display_content && (
          <div className="text-xl font-medium text-center p-4 bg-gray-50 rounded-lg mb-4">
            {currentItem.display_content}
          </div>
        )}

        {phase === "idle" && (
          <NeoButton onClick={startRecording} className="w-full">
            Start Recording
          </NeoButton>
        )}

        {phase === "recording" && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-red-500">
              <span className="animate-pulse">●</span>
              <span>Recording...</span>
            </div>
            <NeoButton onClick={stopAndUpload} className="w-full bg-red-50 border-red-300">
              Stop & Submit
            </NeoButton>
          </div>
        )}

        {phase === "uploading" && (
          <p className="text-center text-gray-500 animate-pulse">Uploading audio...</p>
        )}

        {phase === "scoring" && (
          <p className="text-center text-gray-500 animate-pulse">Analyzing your speech...</p>
        )}

        {phase === "done_item" && (
          <div className="space-y-3">
            {itemScore?.computed_score != null && (
              <div className="text-center">
                <p className="text-sm text-gray-500">Score</p>
                <p className="text-3xl font-bold text-blue-600">{Math.round(itemScore.computed_score)}</p>
              </div>
            )}
            {itemScore?.asr_transcript && (
              <p className="text-sm text-gray-600 italic">&ldquo;{itemScore.asr_transcript}&rdquo;</p>
            )}
            <NeoButton onClick={nextItem} className="w-full">
              {itemIdx + 1 >= allItems.length ? "Complete Baseline" : "Next Item →"}
            </NeoButton>
          </div>
        )}
      </NeoCard>
    </div>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd /d/Developer/sppech-therapy-final/client
npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors for `app/patient/baseline/page.tsx`

- [ ] **Step 4: Commit**

```bash
git add client/app/patient/baseline/page.tsx
git commit -m "feat: replace baseline self-rating UI with ML audio upload and polling flow"
```

---

## Self-Review

### Spec coverage check

| Requirement (from backendflow.md) | Task |
|---|---|
| Remove prompt_scoring and speech_target joins | Task 1 |
| Read from consolidated prompt table | Task 1 |
| Use rule_low_conf_threshold from weights | Task 2 |
| Load defect_pa_threshold | Task 3 |
| Load adaptive_threshold per-prompt override | Task 3 |
| Load emotion_weights_config | Task 3 |
| Upsert patient_task_progress | Task 4 |
| Upsert session_emotion_summary | Task 5 |
| Create therapist_notification on review_recommended | Task 6 |
| Create therapist_notification on patient register | Task 6 |
| Create AudioFile row on upload | Task 7 |
| PlanRevisionHistory on generate | Task 8 |
| PlanRevisionHistory on approve/add/remove/reorder | Task 8 |
| Baseline: filter clinician_rated | Task 10 |
| Baseline: session start endpoint | Task 10 |
| Baseline: per-item audio upload | Task 10 |
| Baseline: polling endpoint | Task 10 |
| Baseline: complete + aggregate into DB | Task 10 |
| Baseline: formula_mode scoring (auto_simple, auto_phoneme_only) | Task 9 |
| Baseline frontend: ML-based audio flow | Task 11 |

### Items not in this plan (deferred)

- `session_prompt_attempt.accuracy_score` backfill from scoring — low priority, polling endpoint covers this
- `audio_file.duration_sec` backfill — requires Celery to update after ASR; deferred to next iteration
- `emotion_weights_config` weighted emotion scoring in analysis.py — config is loaded (Task 3) but the emotion weights are not yet applied to the final engagement score formula (the SpeechBrain model returns its own emotion_score; re-weighting requires mapping model outputs to config weights per age_group)
- Dashboard therapist notifications feed — model + data exist, UI endpoint not built
- Progress API preference for `session_emotion_summary` over raw queries — deferred

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-06-backend-v2-alignment.md`.**

**Two execution options:**

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks

**2. Inline Execution** — execute tasks in this session using executing-plans

Which approach?
