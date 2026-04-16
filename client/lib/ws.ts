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
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_DELAY_MS = 2000;
const STABLE_CONNECTION_RESET_MS = 10000;

export interface ScoreReadyPayload extends AttemptScore {
  attempt_id: string;
}

type ScoreHandler = (data: ScoreReadyPayload) => void;
type MessageHandler = (data: unknown) => void;
type ReconnectHandler = (attempt: number) => void;
type FallbackHandler = () => void;

function getToken(): string | null {
  return useAuthStore.getState().token;
}

function shouldSendTokenOnSocket(): boolean {
  const { protocol, hostname } = new URL(WS_URL);
  return protocol === "wss:" || hostname === "localhost" || hostname === "127.0.0.1";
}

export interface WebSocketHandle {
  disconnect: () => void;
}

export function createWebSocket(
  patientId: string,
  onScore: ScoreHandler,
  onMessage?: MessageHandler,
  onReconnect?: ReconnectHandler,
  onFallback?: FallbackHandler
): WebSocketHandle | null {
  if (typeof window === "undefined") return null;

  let intentionalClose = false;
  let reconnectAttempts = 0;
  let ws: WebSocket | null = null;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let stableConnectionTimer: ReturnType<typeof setTimeout> | null = null;
  let connectTimer: ReturnType<typeof setTimeout> | null = null;

  function sendAuth(socket: WebSocket) {
    const token = getToken();
    if (token && shouldSendTokenOnSocket()) {
      socket.send(JSON.stringify({ type: "auth", token }));
    }
  }

  function openSocket() {
    try {
      ws = new WebSocket(`${WS_URL}/ws/${patientId}`);

      ws.onopen = () => {
        sendAuth(ws!);
        if (stableConnectionTimer !== null) {
          clearTimeout(stableConnectionTimer);
        }
        stableConnectionTimer = setTimeout(() => {
          reconnectAttempts = 0;
          stableConnectionTimer = null;
        }, STABLE_CONNECTION_RESET_MS);
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        onMessage?.(data);
        if (data.type === "score_ready") onScore(data as ScoreReadyPayload);
      };

      ws.onclose = (evt) => {
        if (intentionalClose) return;
        if (stableConnectionTimer !== null) {
          clearTimeout(stableConnectionTimer);
          stableConnectionTimer = null;
        }
        // Only reconnect on unexpected closes
        if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttempts++;
          onReconnect?.(reconnectAttempts);
          reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
        } else {
          onFallback?.();
        }
      };
    } catch {
      if (!intentionalClose && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++;
        onReconnect?.(reconnectAttempts);
        reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS);
      } else {
        onFallback?.();
      }
    }
  }

  function connect() {
    if (intentionalClose || connectTimer !== null) return;
    // Defer initial connection so React dev remounts can cancel cleanly before the browser opens the socket.
    connectTimer = setTimeout(() => {
      connectTimer = null;
      if (intentionalClose) return;
      openSocket();
    }, 0);
  }

  connect();

  return {
    disconnect() {
      intentionalClose = true;
      if (connectTimer !== null) {
        clearTimeout(connectTimer);
        connectTimer = null;
      }
      if (reconnectTimer !== null) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (stableConnectionTimer !== null) {
        clearTimeout(stableConnectionTimer);
        stableConnectionTimer = null;
      }
      ws?.close();
      ws = null;
    },
  };
}
