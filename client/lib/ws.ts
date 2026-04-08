import { useAuthStore } from "@/store/auth";
import type { AttemptScore } from "@/types";

function resolveWsUrl(): string {
  const configured = process.env.NEXT_PUBLIC_WS_URL;
  if (configured) return configured;

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;
  if (apiUrl) {
    const url = new URL(apiUrl);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    return url.origin;
  }

  return "ws://localhost:8000";
}

const WS_URL = resolveWsUrl();

export interface ScoreReadyPayload extends AttemptScore {
  attempt_id: string;
}

type ScoreHandler = (data: ScoreReadyPayload) => void;

function getToken(): string | null {
  return useAuthStore.getState().token;
}

function shouldSendTokenOnSocket(): boolean {
  const { protocol, hostname } = new URL(WS_URL);
  return protocol === "wss:" || hostname === "localhost" || hostname === "127.0.0.1";
}

export function createWebSocket(patientId: string, onScore: ScoreHandler): WebSocket | null {
  if (typeof window === "undefined") return null;
  const token = getToken();
  try {
    const ws = new WebSocket(`${WS_URL}/ws/${patientId}`);
    ws.onopen = () => {
      if (token && shouldSendTokenOnSocket()) {
        ws.send(JSON.stringify({ type: "auth", token }));
      }
    };
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "score_ready") onScore(data as ScoreReadyPayload);
    };
    return ws;
  } catch {
    return null;
  }
}
