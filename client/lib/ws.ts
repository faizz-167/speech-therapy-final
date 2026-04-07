import { useAuthStore } from "@/store/auth";
import type { AttemptScore } from "@/types";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

type ScoreHandler = (data: AttemptScore) => void;

function getToken(): string | null {
  return useAuthStore.getState().token;
}

export function createWebSocket(patientId: string, onScore: ScoreHandler): WebSocket | null {
  if (typeof window === "undefined") return null;
  const token = getToken();
  try {
    const ws = new WebSocket(`${WS_URL}/ws/${patientId}`);
    ws.onopen = () => {
      if (token) {
        ws.send(JSON.stringify({ type: "auth", token }));
      }
    };
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "score_ready") onScore(data);
    };
    return ws;
  } catch {
    return null;
  }
}
