import { PaperCard } from "@/components/usgc";
import { useConnectedPeripherals } from "../ws/providers/PeripheralProvider";

function formatTimestamp(timestamp: number) {
  return new Date(timestamp).toLocaleTimeString();
}

export function PeripheralSnapshots() {
  const peripherals = useConnectedPeripherals();
  const items = Object.entries(peripherals).sort(
    ([, left], [, right]) => right.ts - left.ts,
  );

  return (
    <PaperCard className="flex h-full flex-col gap-5 select-none">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <p className="usgc-kicker">Peripheral Snapshots</p>
          <h2 className="font-tomorrow text-2xl tracking-[0.1em]">
            Latest Peripheral Data
          </h2>
        </div>
        <p className="text-muted-foreground font-mono text-[0.72rem] tracking-[0.18em] uppercase">
          {items.length} Captured Units
        </p>
      </div>

      <div className="usgc-scroll-panel max-h-screen overflow-y-auto">
        {items.length === 0 ? (
          <div className="text-muted-foreground p-4 text-xs">
            No peripheral snapshots have been captured yet.
          </div>
        ) : (
          <table className="usgc-table">
            <thead>
              <tr>
                <th className="px-2 py-1 text-left">Peripheral</th>
                <th className="px-2 py-1 text-left">Last Update</th>
                <th className="px-2 py-1 text-left">Tags</th>
                <th className="px-2 py-1 text-left">Payload</th>
              </tr>
            </thead>
            <tbody>
              {items.map(([id, peripheral]) => (
                <tr key={id}>
                  <td className="px-2 py-1 whitespace-nowrap">
                    {peripheral.info.id ?? "unknown"}
                  </td>
                  <td className="px-2 py-1 whitespace-nowrap">
                    {formatTimestamp(peripheral.ts)}
                  </td>
                  <td className="px-2 py-1">
                    {peripheral.info.tags.length > 0 ? (
                      <ul className="space-y-1">
                        {peripheral.info.tags.map((tag, index) => (
                          <li key={`${tag.name}-${index}`}>
                            <span className="text-muted-foreground">
                              {tag.variant}/
                            </span>
                            {tag.name}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <span className="text-muted-foreground">No tags</span>
                    )}
                  </td>
                  <td className="px-2 py-1">
                    <pre className="whitespace-pre-wrap">
                      {JSON.stringify(peripheral.last_data ?? {}, null, 2)}
                    </pre>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </PaperCard>
  );
}
