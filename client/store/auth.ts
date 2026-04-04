import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

interface AuthState {
  token: string | null;
  role: "therapist" | "patient" | null;
  userId: string | null;
  fullName: string | null;
  hydrated: boolean;
  setAuth: (token: string, role: "therapist" | "patient", userId: string, fullName: string) => void;
  clearAuth: () => void;
  setHydrated: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      role: null,
      userId: null,
      fullName: null,
      hydrated: false,
      setAuth: (token, role, userId, fullName) => set({ token, role, userId, fullName }),
      clearAuth: () => set({ token: null, role: null, userId: null, fullName: null }),
      setHydrated: () => set({ hydrated: true }),
    }),
    {
      name: "auth-storage",
      storage: createJSONStorage(() => localStorage),
      onRehydrateStorage: () => (state) => { state?.setHydrated(); },
    }
  )
);
