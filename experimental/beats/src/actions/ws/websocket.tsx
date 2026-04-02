import {
  createContext,
  useCallback,
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
  sendNavigationControl: (
    command: "browse" | "activate" | "alternate_activate",
    browseStep?: number,
  ) => boolean;
  sendSensorControl: (sensorKey: string, sensorValue: number | null) => boolean;
};

const WSContext = createContext<WSContextValue>({
  socket: null,
  readyState: WebSocket.CLOSED,
  sendNavigationControl: () => false,
  sendSensorControl: () => false,
});

interface WSProviderProps {
  url: string | null;
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

      if (!url) {
        socketRef.current = null;
        setSocket(null);
        setReadyState(WebSocket.CLOSED);
        return;
      }

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

        void decodeMessageData(ev.data)
          .then((buffer) => {
            if (
              buffer === null ||
              socketRef.current !== ws ||
              attemptRef.current !== attempt
            ) {
              return;
            }

            const decoded = decodeStreamEvent(buffer);
            if (decoded) {
              stream.next(decoded);
            }
          })
          .catch((err) => {
            console.error("WebSocket message parse error:", err, ev.data);
          });
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

  const sendNavigationControl = useCallback<
    WSContextValue["sendNavigationControl"]
  >((command, browseStep = 0) => {
    const ws = socketRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      return false;
    }

    ws.send(
      JSON.stringify({
        kind: "control",
        command,
        browse_step: browseStep,
      }),
    );
    return true;
  }, []);

  const sendSensorControl = useCallback<WSContextValue["sendSensorControl"]>(
    (sensorKey, sensorValue) => {
      const ws = socketRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        return false;
      }

      ws.send(
        JSON.stringify({
          kind: "control",
          command: "sensor_update",
          sensor_key: sensorKey,
          sensor_value: sensorValue,
          clear: sensorValue === null,
        }),
      );
      return true;
    },
    [],
  );

  return (
    <WSContext.Provider
      value={{ socket, readyState, sendNavigationControl, sendSensorControl }}
    >
      {children}
    </WSContext.Provider>
  );
}

export function useWS() {
  return useContext(WSContext);
}

async function decodeMessageData(data: unknown): Promise<ArrayBuffer | null> {
  if (data instanceof ArrayBuffer) {
    return data;
  }

  if (data instanceof Blob) {
    if (typeof data.arrayBuffer === "function") {
      return data.arrayBuffer();
    }
    return readBlobAsArrayBuffer(data);
  }

  return null;
}

function readBlobAsArrayBuffer(blob: Blob): Promise<ArrayBuffer> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => {
      reject(reader.error ?? new Error("Failed to read websocket blob"));
    };
    reader.onload = () => {
      if (reader.result instanceof ArrayBuffer) {
        resolve(reader.result);
        return;
      }
      reject(new Error("Websocket blob reader returned a non-binary result"));
    };
    reader.readAsArrayBuffer(blob);
  });
}
