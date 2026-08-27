"use client";
import { useEffect, useRef, useCallback } from "react";
import { WSMessage } from "@/types";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8000/ws/live";

type Handler = (msg: WSMessage) => void;

export function useWebSocket(onMessage: Handler) {
  const wsRef    = useRef<WebSocket | null>(null);
  const handlerRef = useRef<Handler>(onMessage);
  handlerRef.current = onMessage;

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      try {
        const msg: WSMessage = JSON.parse(e.data);
        handlerRef.current(msg);
      } catch { /* ignore malformed */ }
    };

    ws.onclose = () => {
      // Reconnect after 2 s
      setTimeout(connect, 2000);
    };

    ws.onerror = () => ws.close();
  }, []);

  useEffect(() => {
    connect();
    return () => wsRef.current?.close();
  }, [connect]);
}
