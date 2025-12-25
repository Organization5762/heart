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

  useEffect(() => {
    isMountedRef.current = true;
    retryRef.current = retryDelay; // reset on URL / config change

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

    const scheduleReconnect = () => {
      if (!isMountedRef.current) return;

      const delay = retryRef.current;
      const nextDelay = Math.min(delay * 2, maxRetryDelay);
      retryRef.current = nextDelay;

      reconnectTimeoutRef.current = window.setTimeout(() => {
        connect();
      }, delay);
    };

    const connect = () => {
      // Make sure we don't keep an old socket alive
      setSocket((prev) => {
        cleanupSocket(prev);
        return prev;
      });

      const ws = new WebSocket(url);
      ws.binaryType = "arraybuffer";
      setSocket(ws);
      setReadyState(ws.readyState);

      ws.onopen = () => {
        retryRef.current = retryDelay; // reset backoff on successful connect
        setReadyState(ws.readyState);
      };

      ws.onmessage = (ev: MessageEvent) => {
        if (!(ev.data instanceof ArrayBuffer)) {
          return;
        }
        try {
          const decoded = decodeStreamEvent(ev.data);
          if (decoded) {
            stream.next(decoded);
          }
        } catch (err) {
          stream.error(err);
          console.error("WebSocket message parse error:", err, ev.data);
        }
      };

      ws.onerror = () => {
        console.log("error");
        // error generally followed by close, but make sure we close + reconnect
        setReadyState(ws.readyState);
        try {
          ws.close();
        } catch {
          // ignore
        }
      };

      ws.onclose = () => {
        console.log("close");
        setReadyState(ws.readyState);
        scheduleReconnect();
      };
    };

    connect();

    return () => {
      isMountedRef.current = false;
      if (reconnectTimeoutRef.current !== null) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      setSocket((prev) => {
        cleanupSocket(prev);
        return null;
      });
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
