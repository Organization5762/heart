import { TechnicalCard } from "@/components/usgc";
import { usePeripheralEvents } from "../ws/providers/PeripheralEventsProvider";

export function EventList() {
  const events = usePeripheralEvents();

  return (
    <TechnicalCard className="flex h-full flex-col gap-5 select-none">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <p className="usgc-kicker text-[#bdb3a6]">Peripheral Events</p>
          <h2 className="font-tomorrow text-2xl tracking-[0.1em] text-[#f6efe6]">
            Signal Log
          </h2>
        </div>
        <p className="font-mono text-[0.72rem] tracking-[0.18em] text-[#bdb3a6] uppercase">
          {events.length} Entries Cached
        </p>
      </div>

      <div className="usgc-scroll-panel max-h-screen overflow-y-auto border-white/20 bg-white/5">
        <table className="usgc-table">
          <thead>
            <tr>
              <th className="px-2 py-1 text-left">Timestamp</th>
              <th className="px-2 py-1 text-left">Type</th>
              <th className="px-2 py-1 text-left">Payload</th>
            </tr>
          </thead>

          <tbody>
            {events.map((evt, idx) => (
              <tr key={idx}>
                <td className="px-2 py-1 whitespace-nowrap">
                  {new Date(evt.ts).toLocaleTimeString()}
                </td>
                <td className="px-2 py-1">{evt.msg.type}</td>
                <td className="px-2 py-1">
                  <pre className="whitespace-pre-wrap">
                    {JSON.stringify(evt.msg.payload, null, 2)}
                  </pre>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </TechnicalCard>
  );
}
