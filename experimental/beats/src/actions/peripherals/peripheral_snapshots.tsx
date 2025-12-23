import { useConnectedPeripherals } from "../ws/providers/PeripheralProvider";

function formatTimestamp(timestamp: number) {
  return new Date(timestamp).toLocaleTimeString();
}

export function PeripheralSnapshots() {
  const peripherals = useConnectedPeripherals();
  const items = Object.entries(peripherals).sort(([, left], [, right]) => right.ts - left.ts);

  return (
    <div className="flex h-full flex-col select-none p-3">
      <h2 className="text-sm font-bold mb-2 text-muted-foreground uppercase">
        Latest Peripheral Data
      </h2>

      <div className="overflow-auto border rounded-md p-2 bg-black/20 max-h-screen overflow-y-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100 mb-10">
        {items.length === 0 ? (
          <div className="text-xs text-muted-foreground">
            No peripheral snapshots have been captured yet.
          </div>
        ) : (
          <table className="w-full text-xs font-mono">
            <thead className="text-muted-foreground border-b">
              <tr>
                <th className="py-1 px-2 text-left">Peripheral</th>
                <th className="py-1 px-2 text-left">Last Update</th>
                <th className="py-1 px-2 text-left">Tags</th>
                <th className="py-1 px-2 text-left">Payload</th>
              </tr>
            </thead>
            <tbody>
              {items.map(([id, peripheral]) => (
                <tr
                  key={id}
                  className="hover:bg-white/5 border-b border-white/5 align-top"
                >
                  <td className="py-1 px-2 whitespace-nowrap">
                    {peripheral.info.id ?? "unknown"}
                  </td>
                  <td className="py-1 px-2 whitespace-nowrap">
                    {formatTimestamp(peripheral.ts)}
                  </td>
                  <td className="py-1 px-2">
                    {peripheral.info.tags.length > 0 ? (
                      <ul className="space-y-1">
                        {peripheral.info.tags.map((tag, index) => (
                          <li key={`${tag.name}-${index}`}>
                            <span className="text-muted-foreground">{tag.variant}/</span>
                            {tag.name}
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <span className="text-muted-foreground">No tags</span>
                    )}
                  </td>
                  <td className="py-1 px-2">
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
    </div>
  );
}
