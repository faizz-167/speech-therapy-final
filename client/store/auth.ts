import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { UserRole } from "@/types/auth";
import { queryClient } from "@/lib/queryClient";

interface AuthState {
  token: string | null;
  role: UserRole | null;
  userId: string | null;
  fullName: string | null;
  hydrated: boolean;
  bootstrapped: boolean;
  sessionExpired: boolean;
  setAuth: (token: string, role: UserRole, userId: string, fullName: string) => void;
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
      setAuth: (token, role, userId, fullName) =>
        {
          queryClient.clear();
          set({ token, role, userId, fullName, bootstrapped: false, sessionExpired: false });
        },
      clearAuth: () =>
        {
          queryClient.clear();
          set({
            token: null,
            role: null,
            userId: null,
            fullName: null,
            bootstrapped: false,
            sessionExpired: false,
          });
        },
      setHydrated: () => set({ hydrated: true }),
      setSessionExpired: (v) => set({ sessionExpired: v }),
      bootstrapAuth: async () => {
        const { token } = get();
        try {
          const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
          const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {};
          const res = await fetch(`${BASE_URL}/auth/me`, {
            credentials: "include",
            headers,
          });
          if (res.ok) {
            const data = await res.json();
            set({
              token,
              userId: data.user_id,
              role: data.role,
              fullName: data.full_name,
              bootstrapped: true,
              sessionExpired: false,
            });
          } else {
            get().clearAuth();
            set({
              bootstrapped: true,
              sessionExpired: res.status === 401,
            });
          }
        } catch {
          get().clearAuth();
          set({ bootstrapped: true });
        }
      },
    }),
    {
      name: "auth-storage",
      storage: createJSONStorage(() => localStorage),
      onRehydrateStorage: () => (state) => { state?.setHydrated(); },
      partialize: (state) => ({
        role: state.role,
        userId: state.userId,
        fullName: state.fullName,
        // token, bootstrapped, and sessionExpired intentionally excluded — re-evaluated on each app load
      }),
    }
  )
);
