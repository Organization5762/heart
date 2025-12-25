import { createContext, useContext, useEffect, useState } from "react";
import { peripheralStream } from "../streams";

type PeripheralEvent = {
  ts: number;
  msg: any;
};

type PeripheralEventList = PeripheralEvent[];

const PeripheralEventsContext = createContext<PeripheralEventList>([]);

export function PeripheralEventsProvider({ children }: { children: React.ReactNode }) {
  const [events, setEvents] = useState<PeripheralEventList>([]);

  useEffect(() => {
    const sub = peripheralStream.subscribe((msg) => {
      setEvents((prev) => {
        const next = [{ ts: Date.now(), msg }, ...prev];
        return next.length > 100 ? next.slice(0, 100) : next;
      });
    });

    return () => sub.unsubscribe();
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
