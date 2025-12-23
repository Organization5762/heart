import { createContext, useContext, useEffect, useState } from "react";
import { peripheralStream } from "../streams";

export type PeripheralTag = {
    name: string;
    variant: string;
    metadata?: Record<string, string>;
  };

export type PeripheralInfo = {
  id?: string | null;
  tags: PeripheralTag[];
};

type PeripheralMap = Record<string, { ts: number; info: PeripheralInfo, last_data: any }>;

const PeripheralContext = createContext<PeripheralMap>({});

export function PeripheralProvider({ children }: { children: React.ReactNode }) {
  const [peripherals, setPeripherals] = useState<PeripheralMap>({});

  useEffect(() => {
    const sub = peripheralStream.subscribe((msg) => {
      const info = msg.payload.peripheral_info;
      const data = msg.payload.data;
      if (!info.id) return;

      setPeripherals((prev) => ({
        ...prev,
        [info.id]: {
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
