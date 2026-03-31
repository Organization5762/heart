import { usePeripheralEvents } from "@/actions/ws/providers/PeripheralEventsProvider";
import { Input } from "@/components/ui/input";
import {
  executeCommand,
  getCommandSuggestions,
  getSensorCommandKey,
  type CommandSuggestion,
  type SensorTerminalAction,
  type SensorTerminalMessage,
} from "@/features/stream-console/terminal-commands";
import type {
  ResolvedSensorChannel,
  SensorOverride,
} from "@/features/stream-console/sensor-simulation";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { ChevronRight, Command, CornerDownLeft } from "lucide-react";

const TERMINAL_LOG_LIMIT = 240;

type TerminalEntry = {
  id: string;
  level: "command" | "error" | "event" | "system";
  text: string;
  time: number;
};

export function SensorCommandTerminal({
  onClearHistory,
  onResetOverride,
  onSelectSensor,
  onUpdateOverride,
  overrides,
  selectedSensor,
  sensors,
}: {
  onClearHistory: () => void;
  onResetOverride: (sensorId: string) => void;
  onSelectSensor: (sensorId: string) => void;
  onUpdateOverride: (sensorId: string, patch: Partial<SensorOverride>) => void;
  overrides: Record<string, SensorOverride>;
  selectedSensor: ResolvedSensorChannel | null;
  sensors: ResolvedSensorChannel[];
}) {
  const events = usePeripheralEvents();
  const [commandValue, setCommandValue] = useState("");
  const [commandHistory, setCommandHistory] = useState<string[]>([]);
  const [commandHistoryIndex, setCommandHistoryIndex] = useState<number | null>(
    null,
  );
  const [suggestionIndex, setSuggestionIndex] = useState(0);
  const [sessionEntries, setSessionEntries] = useState<TerminalEntry[]>(() => [
    createTerminalEntry(
      "system",
      "Mock terminal online. Type `help` to inspect supported commands.",
    ),
    createTerminalEntry(
      "system",
      "Use `sensors` to browse keys, `select <sensor-key>` to focus one, then `set`, `expr`, or `preset` to adjust the mock.",
    ),
  ]);

  const viewportRef = useRef<HTMLDivElement | null>(null);
  const suggestions = getCommandSuggestions(commandValue, sensors);
  const eventEntries = [...events]
    .reverse()
    .map((event) =>
      createTerminalEntry(
        "event",
        formatPeripheralEvent(
          event.msg.payload.peripheralInfo.id,
          event.msg.payload.data,
        ),
        event.ts,
        `${event.ts}:${event.msg.payload.peripheralInfo.id ?? "unknown"}:${JSON.stringify(event.msg.payload.data) ?? "null"}`,
      ),
    );
  const entries = [...sessionEntries, ...eventEntries]
    .sort((left, right) => left.time - right.time)
    .slice(-TERMINAL_LOG_LIMIT);

  function appendEntries(nextEntries: TerminalEntry[]) {
    setSessionEntries((previous) => {
      const combined = [...previous, ...nextEntries];
      if (combined.length <= TERMINAL_LOG_LIMIT) {
        return combined;
      }
      return combined.slice(combined.length - TERMINAL_LOG_LIMIT);
    });
  }

  useEffect(() => {
    if (!viewportRef.current) {
      return;
    }

    viewportRef.current.scrollTop = viewportRef.current.scrollHeight;
  }, [entries]);

  function applyActions(actions: SensorTerminalAction[]) {
    for (const action of actions) {
      if (action.type === "select-sensor") {
        onSelectSensor(action.sensorId);
        continue;
      }

      if (action.type === "update-override") {
        onUpdateOverride(action.sensorId, action.patch);
        continue;
      }

      if (action.type === "reset-override") {
        onResetOverride(action.sensorId);
        continue;
      }

      if (action.type === "clear-history") {
        onClearHistory();
      }
    }
  }

  function submitCommand(rawCommand: string) {
    const normalizedCommand = rawCommand.trim();
    if (!normalizedCommand) {
      return;
    }

    appendEntries([createTerminalEntry("command", `$ ${normalizedCommand}`)]);

    const result = executeCommand(normalizedCommand, {
      overrides,
      selectedSensor,
      sensors,
    });

    applyActions(result.actions);
    appendEntries(result.messages.map(mapMessageToEntry));
    setCommandHistory((previous) =>
      [normalizedCommand, ...previous].slice(0, 24),
    );
    setCommandHistoryIndex(null);
    setCommandValue("");
    setSuggestionIndex(0);
  }

  function acceptSuggestion(suggestion: CommandSuggestion | undefined) {
    if (!suggestion) {
      return;
    }

    setCommandValue(suggestion.value);
    setSuggestionIndex(0);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      submitCommand(commandValue);
      return;
    }

    if (event.key === "Tab" && suggestions.length > 0) {
      event.preventDefault();
      acceptSuggestion(suggestions[suggestionIndex] ?? suggestions[0]);
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (suggestions.length > 0) {
        setSuggestionIndex((previous) => (previous + 1) % suggestions.length);
        return;
      }

      if (commandHistory.length === 0) {
        return;
      }

      if (commandHistoryIndex === null) {
        return;
      }

      const nextIndex = commandHistoryIndex - 1;
      if (nextIndex < 0) {
        setCommandHistoryIndex(null);
        setCommandValue("");
        return;
      }

      setCommandHistoryIndex(nextIndex);
      setCommandValue(commandHistory[nextIndex] ?? "");
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (suggestions.length > 0) {
        setSuggestionIndex((previous) =>
          previous === 0 ? suggestions.length - 1 : previous - 1,
        );
        return;
      }

      if (commandHistory.length === 0) {
        return;
      }

      const nextIndex =
        commandHistoryIndex === null
          ? 0
          : Math.min(commandHistoryIndex + 1, commandHistory.length - 1);
      setCommandHistoryIndex(nextIndex);
      setCommandValue(commandHistory[nextIndex] ?? "");
    }
  }

  return (
    <section className="rounded-[1.35rem] border border-[#404754] bg-[linear-gradient(180deg,_rgba(9,13,18,0.98),_rgba(5,8,12,1))] shadow-[inset_0_1px_0_rgba(255,255,255,0.05),0_24px_60px_rgba(0,0,0,0.45)]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#20262f] px-4 py-3">
        <div>
          <p className="font-tomorrow text-[10px] tracking-[0.24em] text-[#6f7d91] uppercase">
            Sensor Terminal
          </p>
          <h3 className="font-tomorrow text-sm tracking-[0.14em] text-slate-100 uppercase">
            Logs and Mock Commands
          </h3>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <TerminalBadge
            label="Focus"
            value={
              selectedSensor
                ? getSensorCommandKey(selectedSensor)
                : "unassigned"
            }
          />
          <TerminalBadge
            label="Mode"
            value={overrides[selectedSensor?.id ?? ""]?.mode ?? "live"}
          />
        </div>
      </div>

      <div
        ref={viewportRef}
        className="h-[320px] overflow-y-auto px-4 py-3 font-mono text-[13px] leading-6"
      >
        {entries.map((entry) => (
          <div
            key={entry.id}
            className="grid grid-cols-[74px_18px_minmax(0,1fr)] gap-3"
          >
            <span className="text-[#556273]">
              {formatTimestamp(entry.time)}
            </span>
            <span className={getEntryGlyphClassName(entry.level)}>
              {getEntryGlyph(entry.level)}
            </span>
            <span className={getEntryTextClassName(entry.level)}>
              {entry.text}
            </span>
          </div>
        ))}
      </div>

      <div className="border-t border-[#20262f] px-4 py-3">
        <div className="mb-2 flex items-center gap-2 text-[11px] text-[#7e8ca1]">
          <Command className="h-3.5 w-3.5" />
          <span>
            Tab completes suggestions, arrows browse matches, Enter executes.
          </span>
        </div>

        <div className="rounded-xl border border-[#303743] bg-[#070a0e] shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
          <div className="flex items-center gap-2 px-3 py-2">
            <ChevronRight className="h-4 w-4 text-emerald-400" />
            <Input
              aria-label="Sensor terminal command"
              autoCapitalize="off"
              autoComplete="off"
              autoCorrect="off"
              className="h-8 border-none bg-transparent px-0 py-0 text-sm text-[#e4ecf7] shadow-none focus-visible:ring-0"
              placeholder="help, sensors, select demo.temperature:value, set 0.35"
              spellCheck={false}
              value={commandValue}
              onChange={(event) => {
                setCommandValue(event.target.value);
                setSuggestionIndex(0);
                setCommandHistoryIndex(null);
              }}
              onKeyDown={handleKeyDown}
            />
            <CornerDownLeft className="h-4 w-4 text-[#667489]" />
          </div>

          {suggestions.length > 0 ? (
            <div className="border-t border-[#20262f] px-2 py-2">
              {suggestions.slice(0, 6).map((suggestion, index) => (
                <button
                  key={suggestion.value}
                  type="button"
                  className={`flex w-full items-center justify-between rounded-lg px-2 py-2 text-left transition ${
                    index === suggestionIndex
                      ? "bg-[#111a24] text-slate-100"
                      : "text-[#92a0b4] hover:bg-[#0d141d]"
                  }`}
                  onMouseDown={(event) => {
                    event.preventDefault();
                    acceptSuggestion(suggestion);
                  }}
                >
                  <span className="font-mono text-xs">{suggestion.value}</span>
                  <span className="ml-4 truncate text-[11px] text-[#6f7d91]">
                    {suggestion.description}
                  </span>
                </button>
              ))}
            </div>
          ) : null}
        </div>

        <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-[#78879a]">
          <QuickHint value="show" />
          <QuickHint value="set 0.80" />
          <QuickHint value="preset pulse" />
          <QuickHint value="expr 0.2 + 0.1 * sin(t * 2)" />
        </div>
      </div>
    </section>
  );
}

function createTerminalEntry(
  level: TerminalEntry["level"],
  text: string,
  time = Date.now(),
  id = `${time}:${level}:${text}`,
): TerminalEntry {
  return {
    id,
    level,
    text,
    time,
  };
}

function mapMessageToEntry(message: SensorTerminalMessage) {
  return createTerminalEntry(
    message.level === "error"
      ? "error"
      : message.level === "system"
        ? "system"
        : "event",
    message.text,
  );
}

function formatPeripheralEvent(
  peripheralId: string | null | undefined,
  payload: unknown,
) {
  const preview =
    payload === null || payload === undefined
      ? "null"
      : (JSON.stringify(payload) ?? String(payload)).slice(0, 120);

  return `RX ${peripheralId ?? "unknown"} ${preview}`;
}

function formatTimestamp(timestamp: number) {
  const date = new Date(timestamp);
  return date.toLocaleTimeString([], {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function getEntryGlyph(level: TerminalEntry["level"]) {
  switch (level) {
    case "command":
      return "$";
    case "error":
      return "!";
    case "event":
      return ">";
    default:
      return "*";
  }
}

function getEntryGlyphClassName(level: TerminalEntry["level"]) {
  switch (level) {
    case "command":
      return "text-emerald-400";
    case "error":
      return "text-rose-400";
    case "event":
      return "text-sky-400";
    default:
      return "text-amber-300";
  }
}

function getEntryTextClassName(level: TerminalEntry["level"]) {
  switch (level) {
    case "command":
      return "text-[#e3edf7]";
    case "error":
      return "text-[#fca5a5]";
    case "event":
      return "text-[#b8d4f5]";
    default:
      return "text-[#d4bd7d]";
  }
}

function QuickHint({ value }: { value: string }) {
  return (
    <div className="rounded-full border border-[#2f3742] bg-[#0b1016] px-3 py-1 font-mono text-[#8ea0b7]">
      {value}
    </div>
  );
}

function TerminalBadge({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-full border border-[#313844] bg-[#0c1117] px-3 py-1.5">
      <span className="font-tomorrow mr-2 text-[9px] tracking-[0.18em] text-[#6f7d91] uppercase">
        {label}
      </span>
      <span className="font-mono text-[11px] text-[#dce6f5]">{value}</span>
    </div>
  );
}
