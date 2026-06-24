# Frontend

**Framework:** Next.js 14 (App Router) + React 19  
**Location:** `client/`

---

## Page Structure

```
client/app/
├── layout.tsx                    # Root layout (fonts, providers)
├── page.tsx                      # Landing page (public)
│
├── login/
│   └── page.tsx                  # Login form (email + password)
│
├── register/
│   ├── therapist/
│   │   └── page.tsx              # Therapist registration form
│   └── patient/
│       └── page.tsx              # Patient registration (requires therapist_code)
│
├── patient/
│   ├── layout.tsx                # Patient shell (sidebar/nav, auth guard)
│   ├── home/
│   │   └── page.tsx              # Patient home: streak, today's tasks, plan status
│   ├── baseline/
│   │   └── page.tsx              # Baseline assessment flow
│   ├── tasks/
│   │   ├── page.tsx              # Today's task list
│   │   └── [assignmentId]/
│   │       └── page.tsx          # Active therapy session (record audio, real-time score)
│   ├── progress/
│   │   └── page.tsx              # Progress charts (accuracy trends, emotions)
│   └── profile/
│       └── page.tsx              # Patient profile, streak display
│
└── therapist/
    ├── layout.tsx                 # Therapist shell (sidebar/nav, auth guard)
    ├── dashboard/
    │   └── page.tsx               # Counts, alerts, pending tasks
    ├── profile/
    │   └── page.tsx               # Therapist profile
    ├── patients/
    │   ├── page.tsx               # Patient list with status badges
    │   └── [id]/
    │       ├── page.tsx           # Patient overview
    │       ├── baseline/
    │       │   └── page.tsx       # View patient's baseline results
    │       ├── plan/
    │       │   └── page.tsx       # Create/edit/approve plan (drag-and-drop)
    │       ├── adaptations/
    │       │   └── page.tsx       # Escalation events, auto-regen history
    │       └── progress/
    │           └── page.tsx       # Patient progress charts
```

---

## State Management

### Zustand (Global / Persistent State)
Located in `client/store/`.

| Store | Purpose |
|-------|---------|
| `authStore` | JWT token, user info (therapist or patient), login/logout actions |
| `sessionStore` | Active therapy session state (session_id, current attempt, queue) |

Zustand stores are persisted to `localStorage` so auth survives page refresh.

### TanStack React Query (Server State)
Used for all API calls: caching, background refetch, loading/error states.

Pattern used throughout:
```typescript
// Fetch data
const { data, isLoading, error } = useQuery({
  queryKey: ["patient-tasks"],
  queryFn: () => api.get("/patient/tasks"),
});

// Mutations
const mutation = useMutation({
  mutationFn: (file: Blob) => api.post(`/session/${sessionId}/attempt`, formData),
  onSuccess: (data) => {
    // start polling for score
    startPolling(data.attempt_id);
  },
});
```

---

## API Client

Located in `client/lib/api.ts` (or similar).

- Base URL from `NEXT_PUBLIC_API_URL` env var
- Attaches JWT token from `authStore` to every request as `Authorization: Bearer {token}`
- Handles 401 → redirects to login
- Handles file uploads with `multipart/form-data`

---

## Real-Time: WebSocket

Used in the active session page (`tasks/[assignmentId]/page.tsx`).

```typescript
useEffect(() => {
  const ws = new WebSocket(`${NEXT_PUBLIC_WS_URL}/ws/${patientId}`);
  ws.onmessage = (event) => {
    const score = JSON.parse(event.data);
    // Update UI with real-time score, adaptive decision
  };
  return () => ws.close();
}, [patientId]);
```

Scores delivered via WebSocket eliminate the need to poll once the patient is actively in a session.

---

## Key Components

Located in `client/components/`.

| Component | Purpose |
|-----------|---------|
| AudioRecorder | Mic capture, visual waveform, sends to `/session/{id}/attempt` |
| ScoreDisplay | Shows final_score, emotion, pass/fail badge |
| TaskCard | Displays assignment info (task name, day, progress) |
| PromptView | Shows prompt instruction + display_content to patient |
| PlanBuilder | Drag-and-drop plan editor (uses @dnd-kit) |
| ProgressChart | Line/bar charts from Recharts for accuracy trends |
| EmotionTimeline | Shows emotion distribution per session |
| NotificationBell | Unread count badge + dropdown |
| PatientStatusBadge | `pending` / `approved` chip |

---

## Custom Hooks

Located in `client/hooks/`.

| Hook | Purpose |
|------|---------|
| `useAuth` | Access auth state, login, logout |
| `useSession` | Manage active therapy session (start, submit attempt, poll score) |
| `useNotifications` | Fetch + mark-read notifications |
| `useWebSocket` | Connect to `/ws/{patient_id}`, handle reconnection |
| `usePolling` | Poll an endpoint at interval until condition is met |

---

## Type Definitions

Located in `client/types/`.

TypeScript interfaces mirror the backend Pydantic schemas:

```typescript
interface Patient {
  patient_id: string;
  full_name: string;
  email: string;
  status: "pending" | "approved";
  current_streak: number;
  longest_streak: number;
  // ...
}

interface AttemptScoreDetail {
  final_score: number;
  speech_score: number;
  engagement_score: number;
  adaptive_decision: "advance" | "stay" | "drop";
  pass_fail: "pass" | "fail";
  dominant_emotion: string;
  // ...
}
```

---

## Environment Variables

`client/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

---

## Auth Guards

Both `patient/layout.tsx` and `therapist/layout.tsx` check `authStore` on mount.
- If no token → redirect to `/login`
- If wrong role → redirect to correct dashboard

---

## Therapist Plan Builder

The plan editor at `therapist/patients/[id]/plan/page.tsx` uses `@dnd-kit`:
- Displays 7 columns (Mon–Sun)
- Tasks are draggable cards
- Drop into a day column to assign day_index
- Reorder within a day changes priority_order
- On drop: calls `PUT /plans/{plan_id}/assignments/{assignment_id}`
- "Generate" button calls `POST /plans/generate` and populates the board
- "Approve" button calls `POST /plans/{plan_id}/approve`

---

## Patient Therapy Session Page

`patient/tasks/[assignmentId]/page.tsx` — the core interaction page:

1. **Load:** Call `GET /session/start` → get queue of prompts
2. **Show prompt:** Display instruction + display_content
3. **Record:** AudioRecorder component captures mic input, tracks:
   - `mic_activated_at` → sent to server
   - `speech_start_at` → detected client-side (silence detection)
4. **Submit:** POST audio to `/session/{id}/attempt`
5. **Wait:** Show loading state; WebSocket receives score OR poll `GET /session/attempt/{id}`
6. **Show result:** ScoreDisplay with score, emotion, pass/fail message
7. **Next:** Load next prompt from queue or show session-complete screen
8. **Escalation:** If session is locked after escalation, show "waiting for therapist review" state

---

## Notifications (Real-Time)

Polling approach (no WebSocket for notifications):
- `useNotifications` hook refetches every 30 seconds
- Unread count shown in nav bell icon
- Clicking opens dropdown with notification list + mark-read actions
