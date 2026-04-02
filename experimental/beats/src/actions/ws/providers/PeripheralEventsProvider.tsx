import {
  createContext,
  startTransition,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import type { StreamEvent } from "../protocol";
import { peripheralStream } from "../streams";

type PeripheralEvent = {
  ts: number;
  msg: Extract<StreamEvent, { type: "peripheral" }>;
};

type PeripheralEventList = PeripheralEvent[];

const MAX_PERIPHERAL_EVENTS = 100;
export const EVENT_BATCH_INTERVAL_MS = 250;

const PeripheralEventsContext = createContext<PeripheralEventList>([]);

export function PeripheralEventsProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [events, setEvents] = useState<PeripheralEventList>([]);
  const pendingEventsRef = useRef<PeripheralEventList>([]);
  const flushTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    const flushPendingEvents = () => {
      flushTimeoutRef.current = null;

      if (pendingEventsRef.current.length === 0) {
        return;
      }

      const pendingEvents = pendingEventsRef.current;
      pendingEventsRef.current = [];

      startTransition(() => {
        setEvents((prev) => {
          const next = [...pendingEvents.reverse(), ...prev];
          return next.length > MAX_PERIPHERAL_EVENTS
            ? next.slice(0, MAX_PERIPHERAL_EVENTS)
            : next;
        });
      });
    };

    const sub = peripheralStream.subscribe((msg) => {
      pendingEventsRef.current.push({ ts: Date.now(), msg });

      if (flushTimeoutRef.current === null) {
        flushTimeoutRef.current = window.setTimeout(
          flushPendingEvents,
          EVENT_BATCH_INTERVAL_MS,
        );
      }
    });

    return () => {
      sub.unsubscribe();
      pendingEventsRef.current = [];
      if (flushTimeoutRef.current !== null) {
        clearTimeout(flushTimeoutRef.current);
        flushTimeoutRef.current = null;
      }
    };
  }, []);

  return (
    <PeripheralEventsContext.Provider value={events}>
      {children}
    </PeripheralEventsContext.Provider>
  );
}

export function usePeripheralEvents() {
  return useContext(PeripheralEventsContext);
}

export function useSpecificPeripheralEvents(peripheralId: string) {
  const events = useContext(PeripheralEventsContext);
  return events.filter(
    (event) => event.msg.payload.peripheralInfo.id === peripheralId,
  );
}
