# Phase 5 — Therapist Notifications Frontend

## Objective

Build the complete therapist notification system on the frontend, consuming the endpoints shipped in Phase 4.1. This makes backend-generated notifications (patient registrations, review-flagged attempts) visible and actionable for therapists.

## Dependencies

- Phase 1 must be completed (shared types, router navigation, shared state components).
- Phase 4.1 must be completed (`GET /therapist/notifications`, `POST /therapist/notifications/{id}/read`, `POST /therapist/notifications/read-all`).

---

## Subtasks

### 5.1 — Notification Center Panel Component

**New file:** `client/components/therapist/NotificationPanel.tsx`

**Execution steps:**
1. Define `Notification` type in `client/types/therapist.ts`:
   ```typescript
   interface Notification {
     id: number;
     notification_type: 'patient_registered' | 'review_flagged' | string;
     message: string;
     is_read: boolean;
     created_at: string;
     patient_id: number | null;
     attempt_id: number | null;
   }
   ```
2. Build `<NotificationPanel />` as a slide-in panel or dropdown:
   - Renders a list of `Notification` items.
   - Unread notifications have a distinct visual treatment (bold text, accent-colored left border).
   - Each notification shows: message, relative timestamp ("3 hours ago"), type icon.
   - Clicking a notification: marks it as read (optimistic update), then triggers deep-link navigation (see 5.4).
   - "Mark all as read" button at the top of the panel.
   - Empty state: "No notifications" when list is empty.
3. Panel is toggled by the notification bell in `<TherapistNav />` (see 5.2).
4. Use `NeoCard` and `NeoButton` for neo-brutalist styling.
5. Call `GET /therapist/notifications` to load data.
6. Call `POST /therapist/notifications/{id}/read` on individual click.
7. Call `POST /therapist/notifications/read-all` on the "Mark all as read" action.

**Validation criteria:**
- Panel renders a list of real notifications from the backend.
- Clicking a notification calls the mark-read endpoint.
- Unread vs read visual distinction is clear.
- "Mark all as read" works and updates UI immediately.

---

### 5.2 — Top-Nav Unread Badge + Polling

**File:** `client/components/therapist/TherapistNav.tsx`

**Execution steps:**
1. Add a notification bell icon button to the therapist nav bar.
2. Display an unread count badge on the bell:
   - Fetch `GET /therapist/notifications?unread_only=true` on mount.
   - Poll every 60 seconds to keep the count fresh (use `setInterval` in a `useEffect` with cleanup).
   - Badge shows count; hide badge when count is 0.
3. Clicking the bell toggles the `<NotificationPanel />` component (render it conditionally below the nav or as an overlay).
4. When the panel is opened, the unread count badge should reflect any read actions made inside the panel.
5. Badge uses `neo-accent` background color for visibility.

**Validation criteria:**
- Badge shows correct unread count on page load.
- Badge updates after marking notifications as read.
- Polling interval is cleared on component unmount (no memory leak).
- Bell button is keyboard-accessible.

---

### 5.3 — Mark-Read and Archive Flow

**This is largely implemented as part of 5.1**, but this subtask covers the edge cases and UX polish:

**Execution steps:**
1. Optimistic update pattern for mark-read:
   - When user clicks a notification → immediately update local state to `is_read = true`.
   - Send `POST /therapist/notifications/{id}/read` in the background.
   - On API error → revert local state and show an inline error banner.
2. Optimistic update for "mark all read":
   - Immediately set all notifications to `is_read = true` in local state.
   - Send `POST /therapist/notifications/read-all`.
   - On API error → revert and show error.
3. If "archive" is not a backend concept yet, do not implement a fake archive. Either hide it or disable it with a tooltip "Coming soon".

**Validation criteria:**
- Optimistic updates make the UI feel instant.
- API errors revert the local state correctly.
- No fake/broken archive action exists in the UI.

---

### 5.4 — Deep-Links from Notification to Patient/Attempt Context

**File:** `client/components/therapist/NotificationPanel.tsx` (update from 5.1)

**Execution steps:**
1. Define navigation targets based on `notification_type`:
   - `patient_registered` (has `patient_id`) → navigate to `/therapist/patients/{patient_id}`.
   - `review_flagged` (has `patient_id` and `attempt_id`) → navigate to `/therapist/patients/{patient_id}/progress` (or a future attempt-detail page when it exists).
   - Unknown type → navigate to `/therapist/patients` as a fallback.
2. When a notification is clicked:
   - Mark as read (optimistic).
   - Close the notification panel.
   - Navigate to the appropriate route using `router.push()`.
3. Add a visual link indicator on each notification card (arrow icon or underlined text) so users know it is clickable.

**Validation criteria:**
- Clicking a `patient_registered` notification opens that patient's detail page.
- Clicking a `review_flagged` notification opens the patient's progress view.
- Navigation uses `router.push()` — no `window.location.href`.
- Panel closes after navigation.

---

## Execution Order

```
5.1 (panel component) must be built first
→ 5.2 (nav badge + polling) — can start after 5.1 interface is defined
→ 5.3 (optimistic updates) — builds directly on 5.1
→ 5.4 (deep-links) — final layer on top of 5.1
```

5.2, 5.3, and 5.4 can overlap once 5.1 is complete.

## Validation Criteria (Phase Complete)

- [ ] Therapist nav shows a notification bell with an unread count badge.
- [ ] Badge updates every 60 seconds via polling.
- [ ] Notification panel opens with a real list of notifications.
- [ ] Clicking a notification marks it as read and navigates to the correct page.
- [ ] "Mark all as read" works end-to-end.
- [ ] Optimistic updates are visible; API errors revert gracefully.
- [ ] No `window.location.href` in notification-related code.
- [ ] Bell and panel are keyboard accessible.
- [ ] `npx tsc --noEmit` passes.
