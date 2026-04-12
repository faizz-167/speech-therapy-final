# Phase 7 — Client Updates

## Objective
Update the Next.js client to handle the new response shapes and adaptive decision values from the backend. Three files change: the type definitions, the tasks list page, and the individual task exercise page.

## Dependencies
- Phase 5 COMPLETED (`GET /patient/tasks` returns `TodayTasksResponse`; `GET /patient/tasks/{assignmentId}/session-state` returns escalation fields).
- Phase 3 COMPLETED (backend publishes `adaptive_decision="escalated"` and `"alternate_prompt"` in WS/poll responses).

## Subtasks

### 7.1 — Add `TodayTasksResponse` type
**File:** `client/lib/api.ts` or `client/types.ts` — wherever `TaskAssignmentOut` is currently typed.

Read the file to find the right location, then add:
```typescript
export interface TodayTasksResponse {
  assignments: TaskAssignmentOut[];
  any_escalated: boolean;
}
```

### 7.2 — Update `TaskExerciseState` type
Find where `TaskExerciseState` (or equivalent) is defined. Add two optional fields:
```typescript
export interface TaskExerciseState {
  session_id: string;
  current_level: string;
  total_prompts: number;
  completed_prompts: number;
  task_complete: boolean;
  current_prompt: PromptOut | null;
  escalated?: boolean;           // NEW
  escalation_message?: string;   // NEW
}
```

### 7.3 — Update `tasks/page.tsx` — use `.assignments` instead of raw array
**File:** `client/app/patient/tasks/page.tsx`

The `GET /patient/tasks` response now has shape `{ assignments: TaskAssignmentOut[], any_escalated: boolean }`.

Find every place that currently reads the response as an array (e.g., `data.map(...)`, `setTasks(data)`, etc.) and change to:
- `setTasks(data.assignments)`
- Store `any_escalated` in local state: `const [anyEscalated, setAnyEscalated] = useState(false)`
- On fetch: `setAnyEscalated(data.any_escalated)`

Also update the TypeScript type of the fetch result from `TaskAssignmentOut[]` to `TodayTasksResponse`.

### 7.4 — Render `any_escalated` full-day locked banner in `tasks/page.tsx`
After state changes from subtask 7.3:

```tsx
{anyEscalated && (
  <div className="border-2 border-black bg-yellow-300 p-4 mb-4 font-bold">
    One of today's tasks requires therapist review before you can continue.
    Check back once your therapist has approved a new plan.
  </div>
)}
```

Place the banner above the task list, below the page header. Use existing neo-brutalist component styles — match the border/shadow pattern from other alert elements in the codebase.

### 7.5 — Handle `escalated` state in `tasks/[assignmentId]/page.tsx`
**File:** `client/app/patient/tasks/[assignmentId]/page.tsx`

**Where to add:** In the function that processes the session-state response (after fetching or after receiving a WS message with `adaptive_decision`).

**Two triggers:**
1. **Session-state response with `escalated=true`:** If the fetched state has `state.escalated === true`, redirect to the tasks list with a toast:
   ```typescript
   if (state.escalated) {
     toast.error("This task has been escalated for therapist review.");
     router.push("/patient/tasks");
     return;
   }
   ```

2. **WS/poll result with `adaptive_decision="escalated"`:** In the score-ready handler, when `score.adaptive_decision === "escalated"`:
   ```typescript
   toast.error("This task has been escalated for therapist review.");
   router.push("/patient/tasks");
   ```

### 7.6 — Handle `alternate_prompt` decision in `tasks/[assignmentId]/page.tsx`
In the score-ready handler, when `score.adaptive_decision === "alternate_prompt"`:

```typescript
toast("Difficulty adjusted — trying a different exercise.", {
  icon: "🔄",   // only if the codebase uses emoji toasts; omit otherwise
});
// Then advance to next prompt as normal (call finishOrAdvance or refetch state)
```

This is a non-blocking notification — the exercise page should continue to the next prompt automatically after showing the toast.

## Execution Plan

1. Read `client/lib/api.ts` and/or `client/types.ts` to find existing type definitions.
2. Add `TodayTasksResponse` type and update `TaskExerciseState` (subtasks 7.1, 7.2).
3. Read `client/app/patient/tasks/page.tsx` in full.
4. Update fetch result handling and state to use `.assignments` and `any_escalated` (subtask 7.3).
5. Add escalation banner UI (subtask 7.4).
6. Read `client/app/patient/tasks/[assignmentId]/page.tsx` in full.
7. Add escalated redirect logic (subtask 7.5).
8. Add alternate_prompt toast (subtask 7.6).
9. Update `status.md`.

## Validation Criteria
- [ ] `TodayTasksResponse` type exists and is used as the return type of the tasks fetch.
- [ ] `TaskExerciseState` has `escalated?: boolean` and `escalation_message?: string`.
- [ ] `tasks/page.tsx` accesses `data.assignments` (not `data` directly) for the task list.
- [ ] `tasks/page.tsx` stores and renders `any_escalated` banner when true.
- [ ] `tasks/[assignmentId]/page.tsx` redirects to `/patient/tasks` with toast when `state.escalated === true`.
- [ ] `tasks/[assignmentId]/page.tsx` redirects with toast when `adaptive_decision === "escalated"` arrives.
- [ ] `tasks/[assignmentId]/page.tsx` shows adjustment toast and advances when `adaptive_decision === "alternate_prompt"`.
- [ ] No TypeScript type errors introduced (run `tsc --noEmit` from `client/` to verify).
- [ ] No existing functionality broken (task list still loads, exercises still flow for non-escalated sessions).
