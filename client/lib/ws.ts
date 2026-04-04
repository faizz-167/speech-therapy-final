const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000";

type ScoreHandler = (data: Record<string, unknown>) => void;

export function createWebSocket(patientId: string, onScore: ScoreHandler): WebSocket | null {
  if (typeof window === "undefined") return null;
  try {
    const ws = new WebSocket(`${WS_URL}/ws/${patientId}`);
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "score_ready") onScore(data);
    };
    return ws;
  } catch {
    return null;
  }
}
