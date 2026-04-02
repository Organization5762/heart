import { createContext, useContext, useEffect, useState } from "react";
import type { StreamEvent } from "../protocol";
import { peripheralStream } from "../streams";

export type PeripheralTag = {
  name: string;
  variant: string;
  metadata?: Record<string, string>;
};

export type PeripheralLocation = {
  x: number;
  y: number;
  z: number;
  time: string | null;
};

export type PeripheralInfo = {
  id?: string | null;
  tags: PeripheralTag[];
  location: PeripheralLocation;
};

type PeripheralSnapshot = {
  ts: number;
  info: PeripheralInfo;
  last_data: unknown;
};

type PeripheralMessage = Extract<StreamEvent, { type: "peripheral" }>;

type PeripheralMap = Record<string, PeripheralSnapshot>;

const PeripheralContext = createContext<PeripheralMap>({});

export function PeripheralProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const [peripherals, setPeripherals] = useState<PeripheralMap>({});

  useEffect(() => {
    const sub = peripheralStream.subscribe((msg: PeripheralMessage) => {
      const info = msg.payload.peripheralInfo;
      const data = msg.payload.data;
      const peripheralId = info.id;
      if (!peripheralId) return;

      setPeripherals((prev) => ({
        ...prev,
        [peripheralId]: {
          ts: Date.now(),
          info,
          last_data: data,
        },
      }));
    });

    return () => sub.unsubscribe();
  }, []);

  return (
    <PeripheralContext.Provider value={peripherals}>
      {children}
    </PeripheralContext.Provider>
  );
}

export function useConnectedPeripherals() {
  return useContext(PeripheralContext);
}
