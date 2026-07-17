import { useEffect, useRef, useState } from "react";
import type { ConnectionState, SessionSocketMessage } from "../types";

function socketUrl(sessionId: string): string {
  const configured = import.meta.env.VITE_WS_BASE_URL?.trim();
  const origin = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}`;
  const base = configured?.startsWith("/") ? `${origin}${configured}` : configured || origin;
  const normalized = base.replace(/^http:/, "ws:").replace(/^https:/, "wss:").replace(/\/$/, "");
  if (window.location.protocol === "https:" && !normalized.startsWith("wss:")) {
    throw new Error("La conexión en tiempo real requiere WSS.");
  }
  const websocketBase = normalized.endsWith("/ws") ? normalized : `${normalized}/ws`;
  return `${websocketBase}/sessions/${encodeURIComponent(sessionId)}`;
}

export default function useSessionSocket(sessionId?: string) {
  const [state, setState] = useState<ConnectionState>("disconnected");
  const [message, setMessage] = useState<SessionSocketMessage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const retries = useRef(0);

  useEffect(() => {
    if (!sessionId) return;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let stopped = false;

    const connect = () => {
      if (stopped) return;
      setState(retries.current ? "reconnecting" : "connecting");
      try {
        socket = new WebSocket(socketUrl(sessionId));
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "No fue posible abrir WebSocket.");
        setState("error");
        return;
      }
      socket.onopen = () => {
        retries.current = 0;
        setError(null);
        setState("connected");
      };
      socket.onmessage = (event) => {
        try {
          setMessage(JSON.parse(event.data) as SessionSocketMessage);
        } catch {
          setError("La API envió una actualización no válida.");
        }
      };
      socket.onerror = () => setError("Se interrumpió la conexión en tiempo real.");
      socket.onclose = (event) => {
        if (stopped) return;
        if (event.code === 1008 || event.code === 4401 || event.code === 4403) {
          setState("error");
          setError("La sesión WebSocket no está autorizada.");
          return;
        }
        retries.current += 1;
        setState("reconnecting");
        const delay = Math.min(1000 * 2 ** (retries.current - 1), 15000);
        reconnectTimer = window.setTimeout(connect, delay);
      };
    };

    connect();
    return () => {
      stopped = true;
      if (reconnectTimer !== null) window.clearTimeout(reconnectTimer);
      socket?.close(1000, "Vista cerrada");
      retries.current = 0;
    };
  }, [sessionId]);

  return { state, message, error };
}
