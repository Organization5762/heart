import { createContext, useContext, useEffect, useState } from "react";
import { peripheralStream } from "../streams";

type PeripheralInfo = {
  id?: string | null;
  tags: any[];
};

type PeripheralMap = Record<string, { ts: number; info: PeripheralInfo }>;

const PeripheralContext = createContext<PeripheralMap>({});

export function PeripheralProvider({ children }: { children: React.ReactNode }) {
  const [peripherals, setPeripherals] = useState<PeripheralMap>({});

  useEffect(() => {
    const sub = peripheralStream.subscribe((msg) => {
      const info = msg.payload.peripheral_info;
      if (!info.id) return;

      setPeripherals((prev) => ({
        ...prev,
        [info.id]: {
          ts: Date.now(),
          info,
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