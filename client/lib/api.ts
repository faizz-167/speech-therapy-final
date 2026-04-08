import { useAuthStore } from "@/store/auth";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const PUBLIC_AUTH_PATHS = new Set([
  "/auth/login",
  "/auth/register/patient",
  "/auth/register/therapist",
]);

export type AuthFailureReason = 401 | 403;

type AuthFailureHandler = (reason: AuthFailureReason) => void;

let authFailureHandler: AuthFailureHandler | null = null;

export class AuthError extends Error {
  constructor(message = "Session expired. Please log in again.") {
    super(message);
    this.name = "AuthError";
  }
}

export function onAuthExpired(handler: AuthFailureHandler | null) {
  authFailureHandler = handler;

  return () => {
    if (authFailureHandler === handler) {
      authFailureHandler = null;
    }
  };
}

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return useAuthStore.getState().token;
}

async function request<T>(
  path: string,
  init: RequestInit & { timeout?: number; handleAuthFailure?: boolean } = {}
): Promise<T> {
  const publicAuthPath = PUBLIC_AUTH_PATHS.has(path);
  const { timeout = 15000, handleAuthFailure = !publicAuthPath, ...rest } = init;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  const token = getToken();
  const headers: Record<string, string> = {
    ...(rest.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!(rest.body instanceof FormData)) headers["Content-Type"] = "application/json";
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      ...rest,
      credentials: "include",
      headers,
      signal: controller.signal,
    });
    if (res.status === 401 && handleAuthFailure) {
      const { clearAuth, setSessionExpired } = useAuthStore.getState();
      clearAuth();
      setSessionExpired(true);
      authFailureHandler?.(401);
      throw new AuthError("Session expired. Please log in again.");
    }

    if (res.status === 403 && handleAuthFailure) {
      authFailureHandler?.(403);
      throw new AuthError("You don't have permission to perform this action.");
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
  get: <T>(path: string, options?: RequestInit & { timeout?: number; handleAuthFailure?: boolean }) =>
    request<T>(path, { ...options, method: "GET" }),
  post: <T>(
    path: string,
    body: unknown,
    options?: RequestInit & { timeout?: number; handleAuthFailure?: boolean }
  ) => request<T>(path, { ...options, method: "POST", body: JSON.stringify(body) }),
  patch: <T>(
    path: string,
    body: unknown,
    options?: RequestInit & { timeout?: number; handleAuthFailure?: boolean }
  ) => request<T>(path, { ...options, method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string, options?: RequestInit & { timeout?: number; handleAuthFailure?: boolean }) =>
    request<T>(path, { ...options, method: "DELETE" }),
  upload: <T>(path: string, form: FormData, options?: RequestInit & { timeout?: number; handleAuthFailure?: boolean }) =>
    request<T>(path, { ...options, method: "POST", body: form }),
};
