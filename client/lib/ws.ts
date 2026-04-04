const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

type ScoreHandler = (data: Record<string, unknown>) => void;

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem("auth-storage");
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.state?.token ?? null;
  } catch {
    return null;
  }
}

export function createWebSocket(patientId: string, onScore: ScoreHandler): WebSocket | null {
  if (typeof window === "undefined") return null;
  const token = getToken();
  if (!token) return null;
  try {
    const ws = new WebSocket(`${WS_URL}/ws/${patientId}`);
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: "auth", token }));
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
