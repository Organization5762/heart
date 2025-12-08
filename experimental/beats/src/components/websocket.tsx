import {
    createContext,
    useContext,
    useEffect,
    useRef,
    useState,
} from "react";
  
  const WSContext = createContext<WebSocket | null>(null);
  
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
    const wsRef = useRef<WebSocket | null>(null);
    const retryRef = useRef(retryDelay);
    const [ready, forceRender] = useState({}); // forces rerender when ws changes
  
    useEffect(() => {
      let isMounted = true;
  
      const connect = () => {
        if (!isMounted) return;
  
        const ws = new WebSocket(url);
        wsRef.current = ws;
  
        ws.addEventListener("open", () => {
          retryRef.current = retryDelay;
          forceRender({});
        });
  
        ws.addEventListener("close", () => {
          if (!isMounted) return;
  
          const delay = retryRef.current;
          const nextDelay = Math.min(delay * 2, maxRetryDelay);
          retryRef.current = nextDelay;
  
          setTimeout(connect, delay);
        });
  
        ws.addEventListener("error", () => {
          ws.close();
        });
      };
  
      connect();
  
      return () => {
        isMounted = false;
        wsRef.current?.close();
      };
    }, [url, retryDelay, maxRetryDelay]);
  
    return (
      <WSContext.Provider value={wsRef.current}>
        {children}
      </WSContext.Provider>
    );
  }
  
  export function useWS() {
    return useContext(WSContext);
  }