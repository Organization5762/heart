import { useDeferredValue, useState } from "react";

import { TechnicalCard } from "@/components/beats-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { usePeripheralEvents } from "../ws/providers/PeripheralEventsProvider";

export function EventList() {
  const events = usePeripheralEvents();
  const [pausedEvents, setPausedEvents] = useState<typeof events | null>(null);
  const [filterKey, setFilterKey] = useState("");
  const [filterValue, setFilterValue] = useState("");
  const isPaused = pausedEvents !== null;
  const displayedEvents = isPaused ? pausedEvents : events;
  const deferredFilterKey = useDeferredValue(filterKey);
  const deferredFilterValue = useDeferredValue(filterValue);
  const filteredEvents = displayedEvents.filter((event) =>
    matchesEventFilter(event, deferredFilterKey, deferredFilterValue),
  );

  return (
    <TechnicalCard className="flex h-full flex-col gap-5 select-none">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <p className="beats-kicker text-[#bdb3a6]">Peripheral Events</p>
          <h2 className="font-tomorrow text-2xl tracking-[0.1em] text-[#f6efe6]">
            Signal Log
          </h2>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-3">
          <p className="font-mono text-[0.72rem] tracking-[0.18em] text-[#bdb3a6] uppercase">
            {filteredEvents.length} Visible / {displayedEvents.length} Cached
          </p>
          <Button
            type="button"
            variant={isPaused ? "default" : "outline"}
            onClick={() =>
              setPausedEvents((current) => (current === null ? events : null))
            }
          >
            {isPaused ? "Resume" : "Pause"}
          </Button>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
        <label className="space-y-2">
          <span className="font-mono text-[0.68rem] tracking-[0.18em] text-[#bdb3a6] uppercase">
            Filter Key
          </span>
          <Input
            aria-label="Event filter key"
            placeholder="id"
            value={filterKey}
            onChange={(event) => setFilterKey(event.target.value)}
          />
        </label>
        <label className="space-y-2">
          <span className="font-mono text-[0.68rem] tracking-[0.18em] text-[#bdb3a6] uppercase">
            Filter Value
          </span>
          <Input
            aria-label="Event filter value"
            placeholder="alpha"
            value={filterValue}
            onChange={(event) => setFilterValue(event.target.value)}
          />
        </label>
      </div>

      <div className="beats-scroll-panel max-h-screen overflow-y-auto border-white/20 bg-white/5">
        <table className="beats-table">
          <thead>
            <tr>
              <th className="px-2 py-1 text-left">Timestamp</th>
              <th className="px-2 py-1 text-left">Type</th>
              <th className="px-2 py-1 text-left">Payload</th>
            </tr>
          </thead>

          <tbody>
            {filteredEvents.length > 0 ? (
              filteredEvents.map((evt, idx) => (
                <tr key={`${evt.ts}:${idx}`}>
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
              ))
            ) : (
              <tr>
                <td
                  className="px-2 py-6 font-mono text-[0.72rem] tracking-[0.12em] text-[#bdb3a6] uppercase"
                  colSpan={3}
                >
                  No events match the current filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </TechnicalCard>
  );
}

function matchesEventFilter(
  event: ReturnType<typeof usePeripheralEvents>[number],
  filterKey: string,
  filterValue: string,
) {
  const normalizedKey = filterKey.trim().toLowerCase();
  const normalizedValue = filterValue.trim().toLowerCase();

  if (!normalizedKey && !normalizedValue) {
    return true;
  }

  const scalarEntries = collectScalarEntries(event.msg.payload);

  return scalarEntries.some(({ key, value }) => {
    const keyMatches = normalizedKey ? key === normalizedKey : true;
    const valueMatches = normalizedValue
      ? value.toLowerCase().includes(normalizedValue)
      : true;
    return keyMatches && valueMatches;
  });
}

function collectScalarEntries(
  input: unknown,
  currentKey?: string,
): Array<{ key: string; value: string }> {
  if (input === null || input === undefined) {
    return currentKey
      ? [{ key: currentKey.toLowerCase(), value: String(input) }]
      : [];
  }

  if (
    typeof input === "string" ||
    typeof input === "number" ||
    typeof input === "boolean"
  ) {
    return currentKey
      ? [{ key: currentKey.toLowerCase(), value: String(input) }]
      : [];
  }

  if (Array.isArray(input)) {
    return input.flatMap((entry) => collectScalarEntries(entry, currentKey));
  }

  if (typeof input === "object") {
    return Object.entries(input).flatMap(([key, value]) =>
      collectScalarEntries(value, key),
    );
  }

  return [];
}
