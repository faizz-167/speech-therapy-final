import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

interface AuthState {
  token: string | null;
  role: "therapist" | "patient" | null;
  userId: string | null;
  fullName: string | null;
  hydrated: boolean;
  bootstrapped: boolean;
  sessionExpired: boolean;
  setAuth: (token: string, role: "therapist" | "patient", userId: string, fullName: string) => void;
  clearAuth: () => void;
  setHydrated: () => void;
  setSessionExpired: (v: boolean) => void;
  bootstrapAuth: () => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      role: null,
      userId: null,
      fullName: null,
      hydrated: false,
      bootstrapped: false,
      sessionExpired: false,
      setAuth: (token, role, userId, fullName) => set({ token, role, userId, fullName }),
      clearAuth: () => set({ token: null, role: null, userId: null, fullName: null, bootstrapped: false, sessionExpired: false }),
      setHydrated: () => set({ hydrated: true }),
      setSessionExpired: (v) => set({ sessionExpired: v }),
      bootstrapAuth: async () => {
        const { token } = get();
        if (!token) {
          set({ bootstrapped: true });
          return;
        }
        try {
          const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
          const res = await fetch(`${BASE_URL}/auth/me`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (res.ok) {
            const data = await res.json();
            set({ userId: data.user_id, role: data.role, fullName: data.full_name, bootstrapped: true });
          } else {
            set({ token: null, role: null, userId: null, fullName: null, bootstrapped: true });
          }
        } catch {
          set({ token: null, role: null, userId: null, fullName: null, bootstrapped: true });
        }
      },
    }),
    {
      name: "auth-storage",
      storage: createJSONStorage(() => localStorage),
      onRehydrateStorage: () => (state) => { state?.setHydrated(); },
      partialize: (state) => ({
        token: state.token,
        role: state.role,
        userId: state.userId,
        fullName: state.fullName,
        // bootstrapped and sessionExpired intentionally excluded — re-evaluated on each app load
      }),
    }
  )
);
