import { usePeripheralEvents } from "../ws/providers/PeripheralEventsProvider";

export function EventList() {
    const events = usePeripheralEvents();
  
    return (
      <div className="flex h-full flex-col select-none p-3">
        <h2 className="text-sm font-bold mb-2 text-muted-foreground uppercase">
          Events
        </h2>
  
        <div className="overflow-auto border rounded-md p-2 bg-black/20">
          <table className="w-full text-xs font-mono">
            <thead className="text-muted-foreground border-b">
              <tr>
                <th className="py-1 px-2 text-left">Timestamp</th>
                <th className="py-1 px-2 text-left">Type</th>
                <th className="py-1 px-2 text-left">Payload</th>
              </tr>
            </thead>
  
            <tbody>
              {events.map((evt, idx) => (
                <tr
                  key={idx}
                  className="hover:bg-white/5 border-b border-white/5"
                >
                  <td className="py-1 px-2 whitespace-nowrap">
                    {new Date(evt.ts).toLocaleTimeString()}
                  </td>
                  <td className="py-1 px-2">{evt.msg.type}</td>
                  <td className="py-1 px-2">
                    <pre className="whitespace-pre-wrap">
                      {JSON.stringify(evt.msg.payload, null, 2)}
                    </pre>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }