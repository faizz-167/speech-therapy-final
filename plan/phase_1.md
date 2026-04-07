# Phase 1 — Contract & Shell Stabilization

## Objective

Establish the foundational infrastructure that every other phase depends on.  
This phase eliminates contract drift risk, hardens auth bootstrapping, and removes primitive navigation/alert patterns — without touching any page-level features.

## Dependencies

None. This is the foundation all other phases build on.

## Subtasks

### 1.1 — Consolidate TypeScript Types into Domain Modules

**Problem:**  
Interfaces are duplicated manually across `client/types/index.ts` and page-local files. The frontend is permanently at risk of silently drifting from backend Pydantic schemas.

**Files to change:**
- Create `client/types/auth.ts`
- Create `client/types/patient.ts`
- Create `client/types/baseline.ts`
- Create `client/types/session.ts`
- Create `client/types/plans.ts`
- Create `client/types/progress.ts`
- Create `client/types/therapist.ts`
- Update `client/types/index.ts` to re-export all domain modules
- Remove all page-local interface definitions (grep for `interface` in `client/app/**`)

**Execution steps:**
1. Audit `client/types/index.ts` and all page files for inline `interface` declarations.
2. For each domain, collect all relevant interfaces and move them into the domain file.
3. Cross-reference every interface against the corresponding `server/app/schemas/*.py` Pydantic model — correct field names and types where they have drifted.
4. Import from domain files in each page, replacing inline declarations.
5. Verify no TypeScript compile errors (`npx tsc --noEmit`).

**Validation criteria:**
- `npx tsc --noEmit` passes with zero errors.
- No `interface` declarations remain in `client/app/**` page files.
- All domain type files exist and are imported by at least one consumer.

---

### 1.2 — Auth Bootstrap Provider — Call `/auth/me` on App Start

**Problem:**  
The frontend never calls `/auth/me`. If a token expires or is revoked, the UI keeps treating the session as valid until an API call fails — with no structured recovery.

**Files to change:**
- `client/store/auth.ts` — add `bootstrapAuth()` action
- `client/app/patient/layout.tsx` — call bootstrap before rendering protected routes
- `client/app/therapist/layout.tsx` — same
- `client/lib/api.ts` — ensure `get<T>` is usable without a stored token during bootstrap

**Execution steps:**
1. Add a `bootstrapped: boolean` and `bootstrapAuth(): Promise<void>` to the Zustand auth store.
2. `bootstrapAuth()` reads the persisted token; if present, calls `GET /auth/me`. On success, populates `userId`, `role`, `fullName`. On 401/403, clears auth state.
3. In both layouts, call `bootstrapAuth()` inside a `useEffect` on mount. Show a loading screen (`<BootstrapLoader />`) until `bootstrapped === true`.
4. Only render the protected layout children once `bootstrapped === true`.
5. Add a `<BootstrapLoader />` component (full-screen spinner with the neo-brutalist palette) to `client/components/ui/`.

**Validation criteria:**
- Expiring a stored JWT and reloading redirects to `/login` instead of staying on the protected page.
- A fresh page load with a valid token does NOT flicker to `/login`.
- `bootstrapped` is `false` during the loading phase and `true` once resolved.

---

### 1.3 — Centralized 401/403 Handler + Session Expiry UX

**Problem:**  
There is no standard recovery path for unauthorized responses. Each page handles errors ad hoc.

**Files to change:**
- `client/lib/api.ts` — intercept 401/403 at the `fetch` wrapper level
- `client/store/auth.ts` — expose `clearAuth()` action
- `client/app/patient/layout.tsx` — listen for auth-cleared event
- `client/app/therapist/layout.tsx` — same

**Execution steps:**
1. In `api.ts`, after every response, check `response.status`:
   - `401` → call `useAuthStore.getState().clearAuth()`, then redirect to `/login`.
   - `403` → redirect to `/login` (role mismatch).
2. Add an `onAuthExpired` callback hook to the api client so layouts can optionally react (e.g., show a "session expired" toast before redirecting).
3. Add `clearAuth()` to the Zustand store: wipes `token`, `role`, `userId`, `fullName`, resets `bootstrapped` to `false`.
4. Test the path: manually clear the token mid-session and trigger an API call — the user should land at `/login` cleanly.

**Validation criteria:**
- Any 401 response from any page clears auth and redirects to `/login`.
- Any 403 response redirects to `/login`.
- No page is left in a broken state (stuck spinner, blank screen) after auth expiry.

---

### 1.4 — Replace `window.location.href`, `alert`, `confirm` Everywhere

**Problem:**  
Several pages use browser-native primitives (`window.location.href`, `alert`, `confirm`) that break the React navigation model and produce ugly native browser UI.

**Files to audit:**
- All files under `client/app/**`
- `client/components/**`

**Execution steps:**
1. Grep for `window.location`, `alert(`, `confirm(` across `client/`.
2. Replace `window.location.href = '/path'` → `router.push('/path')` (import `useRouter` from `next/navigation`).
3. Replace `alert(message)` → schedule for Phase 6.2 toast system, but for now add a simple inline error/success banner state (e.g., `const [banner, setBanner] = useState<string | null>(null)`).
4. Replace `confirm(message)` → replace with a `<ConfirmModal />` component in `client/components/ui/ConfirmModal.tsx`. The modal accepts `message`, `onConfirm`, `onCancel` props and follows neo-brutalist styling.
5. Wire the `<ConfirmModal />` into every page that previously used `confirm(`.

**Validation criteria:**
- `grep -r "window.location.href\|alert(\|confirm(" client/` returns zero results.
- All confirmation flows use `<ConfirmModal />`.
- All post-action navigations use `router.push()`.

---

### 1.5 — Standardize Loading, Empty, and Error State Components

**Problem:**  
Each page implements its own loading spinner, empty state, and error display ad hoc, leading to visual inconsistency and duplicated code.

**Files to create:**
- `client/components/ui/LoadingState.tsx` — spinner with optional label
- `client/components/ui/EmptyState.tsx` — icon + heading + subtext + optional CTA
- `client/components/ui/ErrorState.tsx` — error icon + message + optional retry button
- `client/components/ui/ConfirmModal.tsx` — created in 1.4

**Execution steps:**
1. Design all three components using existing neo-brutalist primitives (`NeoCard`, `NeoButton`).
2. `<LoadingState label="Loading..." />` — centered spinner, configurable label.
3. `<EmptyState icon={...} heading="..." subtext="..." cta={{ label, onClick }} />` — flexible empty state.
4. `<ErrorState message="..." onRetry={fn} />` — shows error message + optional retry button.
5. Audit each page in `client/app/**` and replace ad hoc loading/error/empty JSX with these shared components.

**Validation criteria:**
- All three components exist and are exported from `client/components/ui/index.ts`.
- No page-level custom spinner or empty-state JSX remains (pages import from `ui/`).
- Visual review passes: states look consistent across patient and therapist areas.

---

## Execution Order

```
1.1 (types) → 1.2 (bootstrap) → 1.3 (auth handler) → 1.4 (nav/alert) → 1.5 (shared states)
```

1.1 should be completed first so all subsequent subtasks use the correct shared types.  
1.2 and 1.3 are sequential (bootstrap must exist before the 401 handler references it).  
1.4 and 1.5 are independent of each other and can run in parallel after 1.3.

## Validation Criteria (Phase Complete)

- [ ] `npx tsc --noEmit` passes with zero errors.
- [ ] Zero instances of `window.location.href`, `alert(`, `confirm(` in `client/`.
- [ ] `/auth/me` is called on every protected-route mount; expired tokens redirect to `/login`.
- [ ] `LoadingState`, `EmptyState`, `ErrorState`, `ConfirmModal` components exist and are used across all pages.
- [ ] All domain type files exist and are fully consumed by at least one page or component each.
