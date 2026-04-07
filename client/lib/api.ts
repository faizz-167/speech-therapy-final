import { useAuthStore } from "@/store/auth";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class AuthError extends Error {
  constructor(message = "Session expired. Please log in again.") {
    super(message);
    this.name = "AuthError";
  }
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem("auth-storage");
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.state?.token ?? null;
  } catch { return null; }
}

async function request<T>(path: string, init: RequestInit & { timeout?: number } = {}): Promise<T> {
  const { timeout = 15000, ...rest } = init;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  const token = getToken();
  const headers: Record<string, string> = {
    ...(rest.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!(rest.body instanceof FormData)) headers["Content-Type"] = "application/json";
  try {
    const res = await fetch(`${BASE_URL}${path}`, { ...rest, headers, signal: controller.signal });
    if (res.status === 401 || res.status === 403) {
      const { clearAuth, setSessionExpired } = useAuthStore.getState();
      clearAuth();
      setSessionExpired(true);
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      throw new AuthError();
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail ?? "Request failed");
    }
    return res.json() as Promise<T>;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form, timeout: 60000 }),
};
