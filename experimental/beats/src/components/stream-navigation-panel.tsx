import { useWS } from "@/actions/ws/websocket";
import { usePeripheralEvents } from "@/actions/ws/providers/PeripheralEventsProvider";
import {
  summarizeNavigationTelemetry,
  type NavigationIntentSnapshot,
} from "@/features/stream-console/navigation-telemetry";
import { cn } from "@/utils/tailwind";
import {
  ChevronLeft,
  ChevronRight,
  Compass,
  CornerDownLeft,
  MoveHorizontal,
  Send,
} from "lucide-react";

export function StreamNavigationPanel() {
  const events = usePeripheralEvents();
  const { readyState, sendNavigationControl } = useWS();
  const summary = summarizeNavigationTelemetry(events);
  const controlsEnabled = readyState === WebSocket.OPEN;

  return (
    <section className="beats-console-panel rounded-[1.5rem] p-4 md:p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <p className="beats-console-kicker font-tomorrow text-[11px] tracking-[0.22em] uppercase">
            Navigation Telemetry
          </p>
          <h2 className="font-tomorrow text-lg tracking-[0.14em] text-slate-100 uppercase">
            Navigation Controls
          </h2>
          <p className="beats-console-copy text-sm leading-6">
            Send browse and mode commands to Heart while monitoring the latest
            navigation activity.
          </p>
        </div>
        <div className="beats-console-card rounded-xl px-3 py-2 text-right">
          <div className="beats-console-kicker font-tomorrow text-[10px] tracking-[0.2em] uppercase">
            State
          </div>
          <div className="beats-console-strong font-mono text-sm">
            {formatModeState(summary.inferredModeState)}
          </div>
        </div>
      </div>

      <div className="mb-4 grid gap-3 md:grid-cols-2 2xl:grid-cols-4">
        <NavigationActionButton
          disabled={!controlsEnabled}
          icon={<ChevronLeft className="h-4 w-4" />}
          label="Previous"
          detail="Browse -1"
          onClick={() => sendNavigationControl("browse", -1)}
        />
        <NavigationActionButton
          disabled={!controlsEnabled}
          icon={<ChevronRight className="h-4 w-4" />}
          label="Next"
          detail="Browse +1"
          onClick={() => sendNavigationControl("browse", 1)}
        />
        <NavigationActionButton
          disabled={!controlsEnabled}
          icon={<Send className="h-4 w-4" />}
          label="Activate"
          detail="Primary"
          onClick={() => sendNavigationControl("activate")}
        />
        <NavigationActionButton
          disabled={!controlsEnabled}
          icon={<CornerDownLeft className="h-4 w-4" />}
          label="Alternate"
          detail="Secondary"
          onClick={() => sendNavigationControl("alternate_activate")}
        />
      </div>

      <div className="mb-4 grid gap-3 md:grid-cols-3">
        <NavigationMetric
          label="Pending Delta"
          value={formatSigned(summary.pendingBrowseOffset)}
          helper="Accumulated browse step not yet committed."
        />
        <NavigationMetric
          label="Last Commit"
          value={formatSigned(summary.lastCommittedDelta)}
          helper="Most recent committed browse delta."
        />
        <NavigationMetric
          label="Last Intent"
          value={
            summary.lastIntent ? formatIntentLabel(summary.lastIntent) : "None"
          }
          helper={summary.lastIntent?.source ?? "Awaiting navigation input."}
        />
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-3">
        <CountChip
          icon={<MoveHorizontal className="h-4 w-4" />}
          label="Browse"
          value={summary.browseCount}
        />
        <CountChip
          icon={<Send className="h-4 w-4" />}
          label="Activate"
          value={summary.activateCount}
        />
        <CountChip
          icon={<CornerDownLeft className="h-4 w-4" />}
          label="Alternate"
          value={summary.alternateCount}
        />
      </div>

      <div className="beats-console-card rounded-xl p-3">
        <div className="mb-3 flex items-center gap-2">
          <Compass className="h-4 w-4 text-sky-500" />
          <h3 className="font-tomorrow text-sm tracking-[0.12em] text-slate-100 uppercase">
            Recent Intents
          </h3>
        </div>
        {summary.recentIntents.length > 0 ? (
          <div className="space-y-2">
            {summary.recentIntents.map((intent, index) => (
              <div
                key={`${intent.ts}:${intent.source}:${index}`}
                className="rounded-xl border border-[var(--beats-chip-border)] bg-[rgba(24,29,36,0.9)] px-3 py-3"
              >
                <div className="flex items-center justify-between gap-3">
                  <span
                    className={cn(
                      "font-tomorrow text-[10px] tracking-[0.16em] uppercase",
                      intent.kind === "browse"
                        ? "text-emerald-300"
                        : intent.kind === "activate"
                          ? "text-amber-300"
                          : "text-rose-300",
                    )}
                  >
                    {formatIntentLabel(intent)}
                  </span>
                  <span className="font-mono text-[0.72rem] text-[#96a3b7]">
                    {new Date(intent.ts).toLocaleTimeString()}
                  </span>
                </div>
                <p className="mt-1 font-mono text-xs text-[#95a2b6]">
                  Source {intent.source}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <div className="beats-console-empty rounded-xl border border-dashed border-[#404754] px-3 py-6 text-sm text-[#95a2b6]">
            Awaiting streamed navigation intents.
          </div>
        )}
      </div>
    </section>
  );
}

function NavigationMetric({
  helper,
  label,
  value,
}: {
  helper: string;
  label: string;
  value: string;
}) {
  return (
    <div className="beats-console-card rounded-xl p-3">
      <div className="beats-console-kicker font-tomorrow text-[10px] tracking-[0.2em] uppercase">
        {label}
      </div>
      <div className="beats-console-strong mt-1 font-mono text-2xl">
        {value}
      </div>
      <div className="mt-1 text-xs text-[#95a2b6]">{helper}</div>
    </div>
  );
}

function NavigationActionButton({
  detail,
  disabled,
  icon,
  label,
  onClick,
}: {
  detail: string;
  disabled: boolean;
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="beats-console-card flex min-h-28 flex-col items-start justify-between rounded-xl border border-[#404754] bg-[#10141a] px-4 py-4 text-left transition hover:bg-[#171c23] disabled:cursor-not-allowed disabled:opacity-50"
    >
      <div className="rounded-full border border-[#39414c] bg-[#0b0f14] p-2.5 text-slate-100">
        {icon}
      </div>
      <div className="min-w-0">
        <div className="font-tomorrow text-sm tracking-[0.1em] text-slate-100 uppercase">
          {label}
        </div>
        <div className="mt-1 text-sm leading-5 text-[#95a2b6]">{detail}</div>
      </div>
    </button>
  );
}

function CountChip({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
}) {
  return (
    <div className="beats-console-card flex items-center gap-3 rounded-xl px-3 py-3">
      <div className="rounded-full border border-[#39414c] bg-[#10141a] p-2 text-slate-100">
        {icon}
      </div>
      <div>
        <div className="beats-console-kicker font-tomorrow text-[10px] tracking-[0.2em] uppercase">
          {label}
        </div>
        <div className="beats-console-strong font-mono text-lg">{value}</div>
      </div>
    </div>
  );
}

function formatSigned(value: number) {
  if (value > 0) {
    return `+${value}`;
  }

  return String(value);
}

function formatModeState(
  state: "idle" | "browsing" | "committed" | "select_mode",
) {
  switch (state) {
    case "browsing":
      return "Browsing";
    case "committed":
      return "Committed";
    case "select_mode":
      return "Select Mode";
    default:
      return "Idle";
  }
}

function formatIntentLabel(intent: NavigationIntentSnapshot) {
  if (intent.kind === "browse") {
    return `Browse ${formatSigned(intent.step)}`;
  }

  if (intent.kind === "activate") {
    return "Activate";
  }

  return "Alternate";
}
