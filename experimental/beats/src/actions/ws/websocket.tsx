import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { Subject } from "rxjs";

import { decodeStreamEvent, StreamEvent } from "./protocol";

export const stream = new Subject<StreamEvent>();

type WSContextValue = {
  socket: WebSocket | null;
  readyState: WebSocket["readyState"];
};

const WSContext = createContext<WSContextValue>({
  socket: null,
  readyState: WebSocket.CLOSED,
});

interface WSProviderProps {
  url: string;
  children: React.ReactNode;
  retryDelay?: number;
  maxRetryDelay?: number;
}

export function WSProvider({
  url,
  children,
  retryDelay = 1000,
  maxRetryDelay = 8000,
}: WSProviderProps) {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [readyState, setReadyState] = useState<WebSocket["readyState"]>(
    WebSocket.CLOSED,
  );

  const retryRef = useRef(retryDelay);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const isMountedRef = useRef(true);
  const socketRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);

  useEffect(() => {
    isMountedRef.current = true;
    retryRef.current = retryDelay;

    const cleanupSocket = (ws: WebSocket | null) => {
      if (!ws) return;
      ws.onopen = null;
      ws.onmessage = null;
      ws.onclose = null;
      ws.onerror = null;
      try {
        ws.close();
      } catch {
        // ignore
      }
    };

    const clearReconnectTimer = () => {
      if (reconnectTimeoutRef.current !== null) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };

    const scheduleReconnect = () => {
      if (!isMountedRef.current || reconnectTimeoutRef.current !== null) return;

      const delay = retryRef.current;
      const nextDelay = Math.min(delay * 2, maxRetryDelay);
      retryRef.current = nextDelay;

      reconnectTimeoutRef.current = window.setTimeout(() => {
        reconnectTimeoutRef.current = null;
        connect();
      }, delay);
    };

    const connect = () => {
      clearReconnectTimer();
      attemptRef.current += 1;
      const attempt = attemptRef.current;

      cleanupSocket(socketRef.current);

      const ws = new WebSocket(url);
      ws.binaryType = "arraybuffer";
      socketRef.current = ws;
      setSocket(ws);
      setReadyState(ws.readyState);

      ws.onopen = () => {
        if (socketRef.current !== ws || attemptRef.current !== attempt) return;
        clearReconnectTimer();
        retryRef.current = retryDelay;
        setReadyState(ws.readyState);
      };

      ws.onmessage = (ev: MessageEvent) => {
        if (socketRef.current !== ws || attemptRef.current !== attempt) return;
        if (!(ev.data instanceof ArrayBuffer)) {
          return;
        }
        try {
          const decoded = decodeStreamEvent(ev.data);
          if (decoded) {
            stream.next(decoded);
          }
        } catch (err) {
          console.error("WebSocket message parse error:", err, ev.data);
        }
      };

      ws.onerror = () => {
        if (socketRef.current !== ws || attemptRef.current !== attempt) return;
        setReadyState(ws.readyState);
        try {
          ws.close();
        } catch {
          // ignore
        }
      };

      ws.onclose = () => {
        if (socketRef.current !== ws || attemptRef.current !== attempt) return;
        socketRef.current = null;
        setSocket((current) => (current === ws ? null : current));
        setReadyState(ws.readyState);
        scheduleReconnect();
      };
    };

    connect();

    return () => {
      isMountedRef.current = false;
      clearReconnectTimer();
      cleanupSocket(socketRef.current);
      socketRef.current = null;
      setSocket(null);
      setReadyState(WebSocket.CLOSED);
    };
  }, [url, retryDelay, maxRetryDelay]);

  return (
    <WSContext.Provider value={{ socket, readyState }}>
      {children}
    </WSContext.Provider>
  );
}

export function useWS() {
  return useContext(WSContext);
}
