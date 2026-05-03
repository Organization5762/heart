import type { PeripheralInfo } from "@/actions/ws/providers/PeripheralProvider";
import { useNavigate } from "@tanstack/react-router";
import { useEffect, useState, type MouseEvent as ReactMouseEvent } from "react";

type PreviewMetric = {
  id: string;
  label: string;
  groupLabel: string;
  signalLabel: string;
  kind: "numeric" | "boolean";
  value: number | boolean;
};

type PreviewMetricGroup = {
  id: string;
  label: string;
  metrics: PreviewMetric[];
};

type SensorContextMenuState = {
  x: number;
  y: number;
  metric: PreviewMetric;
};

const MAX_PREVIEW_METRICS = 6;
const FALLBACK_GROUP_LABEL = "General";

function formatMetricSegment(segment: string) {
  return segment.replaceAll("_", " ");
}

function toTitleCase(value: string) {
  return value.replace(/\b\w/g, (character) => character.toUpperCase());
}

function buildMetricLabels(path: string[]) {
  const [groupSegment, ...signalSegments] = path;
  const normalizedGroup = groupSegment
    ? toTitleCase(formatMetricSegment(groupSegment))
    : FALLBACK_GROUP_LABEL;
  const normalizedSignal =
    signalSegments.length > 0
      ? signalSegments.map(formatMetricSegment).join(".")
      : formatMetricSegment(groupSegment ?? FALLBACK_GROUP_LABEL);

  return {
    groupLabel: normalizedGroup,
    signalLabel: normalizedSignal,
  };
}

export function collectPreviewMetrics(payload: unknown): PreviewMetric[] {
  const metrics: PreviewMetric[] = [];

  function visit(value: unknown, path: string[]) {
    if (metrics.length >= MAX_PREVIEW_METRICS) {
      return;
    }

    if (typeof value === "number" && Number.isFinite(value)) {
      const labels = buildMetricLabels(path);
      metrics.push({
        id: path.join("."),
        label: path.join("."),
        groupLabel: labels.groupLabel,
        signalLabel: labels.signalLabel,
        kind: "numeric",
        value,
      });
      return;
    }

    if (typeof value === "boolean") {
      const labels = buildMetricLabels(path);
      metrics.push({
        id: path.join("."),
        label: path.join("."),
        groupLabel: labels.groupLabel,
        signalLabel: labels.signalLabel,
        kind: "boolean",
        value,
      });
      return;
    }

    if (Array.isArray(value)) {
      value.forEach((entry, index) => {
        visit(entry, [...path, String(index)]);
      });
      return;
    }

    if (value && typeof value === "object") {
      Object.entries(value as Record<string, unknown>).forEach(
        ([key, entry]) => {
          visit(entry, [...path, key]);
        },
      );
    }
  }

  visit(payload, []);
  return metrics.filter((metric) => metric.label.length > 0);
}

export function groupPreviewMetrics(
  metrics: PreviewMetric[],
): PreviewMetricGroup[] {
  const grouped = new Map<string, PreviewMetricGroup>();

  metrics.forEach((metric) => {
    const existing = grouped.get(metric.groupLabel);
    if (existing) {
      existing.metrics.push(metric);
      return;
    }

    grouped.set(metric.groupLabel, {
      id: metric.groupLabel.toLowerCase().replaceAll(/\s+/g, "-"),
      label: metric.groupLabel,
      metrics: [metric],
    });
  });

  return Array.from(grouped.values());
}

function formatMetricValue(metric: PreviewMetric) {
  if (metric.kind === "boolean") {
    return metric.value ? "On" : "Off";
  }

  return typeof metric.value === "number"
    ? metric.value.toFixed(2)
    : String(metric.value);
}

function metricWidth(metric: PreviewMetric) {
  if (metric.kind === "boolean") {
    return metric.value ? 100 : 18;
  }

  if (typeof metric.value !== "number") {
    return 18;
  }

  return Math.max(
    12,
    Math.min(100, Math.round(Math.abs(Math.tanh(metric.value)) * 100)),
  );
}

export function GenericSensorPeripheralView({
  className,
  lastData,
  peripheral,
}: {
  className?: string;
  lastData: unknown;
  peripheral: PeripheralInfo;
}) {
  const navigate = useNavigate();
  const metrics = collectPreviewMetrics(lastData);
  const metricGroups = groupPreviewMetrics(metrics);
  const [contextMenu, setContextMenu] = useState<SensorContextMenuState | null>(
    null,
  );

  useEffect(() => {
    if (!contextMenu) {
      return;
    }

    function dismissMenu() {
      setContextMenu(null);
    }

    function dismissOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setContextMenu(null);
      }
    }

    window.addEventListener("click", dismissMenu);
    window.addEventListener("scroll", dismissMenu, true);
    window.addEventListener("keydown", dismissOnEscape);

    return () => {
      window.removeEventListener("click", dismissMenu);
      window.removeEventListener("scroll", dismissMenu, true);
      window.removeEventListener("keydown", dismissOnEscape);
    };
  }, [contextMenu]);

  function openContextMenu(
    event: ReactMouseEvent<HTMLDivElement>,
    metric: PreviewMetric,
  ) {
    event.preventDefault();
    event.stopPropagation();
    setContextMenu({
      x: event.clientX,
      y: event.clientY,
      metric,
    });
  }

  function openSensorDeck(metric: PreviewMetric) {
    const peripheralId = peripheral.id ?? "unknown";
    setContextMenu(null);
    void navigate({
      to: "/peripherals/connected",
      hash: "sensor-deck",
      search: () => ({
        sensor: `${peripheralId}:${metric.label}`,
      }),
    });
  }

  if (metrics.length === 0) {
    return (
      <div
        className={
          "border-border bg-background/60 text-foreground flex flex-col gap-3 border p-3 text-xs " +
          (className ?? "")
        }
      >
        <div className="flex items-center justify-between gap-2">
          <div className="flex flex-col">
            <span className="text-muted-foreground font-mono text-[0.7rem] tracking-wide uppercase">
              Payload Monitor
            </span>
            <span className="font-mono text-sm">
              {peripheral.id ?? "unknown_peripheral"}
            </span>
          </div>
          <span className="text-muted-foreground font-mono text-[0.7rem] uppercase">
            Raw
          </span>
        </div>
        <pre className="border-border/70 bg-background/80 overflow-x-auto border p-3 font-mono text-[0.68rem] leading-5 whitespace-pre-wrap text-slate-200">
          {JSON.stringify(lastData, null, 2) ?? "null"}
        </pre>
      </div>
    );
  }

  return (
    <div
      className={
        "border-border bg-background/60 text-foreground relative flex flex-col gap-3 border p-3 text-xs " +
        (className ?? "")
      }
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex flex-col">
          <span className="text-muted-foreground font-mono text-[0.7rem] tracking-wide uppercase">
            Sensor Preview
          </span>
          <span className="font-mono text-sm">
            {peripheral.id ?? "unknown_peripheral"}
          </span>
        </div>
        <span className="text-muted-foreground font-mono text-[0.7rem] uppercase">
          {metrics.length} metrics
        </span>
      </div>

      <div className="grid gap-3">
        {metricGroups.map((group) => (
          <section
            key={group.id}
            className="border-border/70 bg-background/70 space-y-2 rounded-sm border p-3"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground font-mono text-[0.68rem] tracking-[0.18em] uppercase">
                {group.label}
              </span>
              <span className="text-muted-foreground font-mono text-[0.68rem] uppercase">
                {group.metrics.length} signals
              </span>
            </div>
            <div className="grid gap-2">
              {group.metrics.map((metric) => (
                <div
                  key={metric.id}
                  className="border-border/70 bg-background/80 rounded-sm border px-3 py-2"
                  onContextMenu={(event) => openContextMenu(event, metric)}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-muted-foreground truncate font-mono text-[0.68rem] uppercase">
                      {metric.signalLabel}
                    </span>
                    <span className="font-mono text-sm text-slate-100">
                      {formatMetricValue(metric)}
                    </span>
                  </div>
                  <div className="bg-border/40 mt-2 h-1.5 overflow-hidden rounded-full">
                    <div
                      className={
                        metric.kind === "boolean"
                          ? "h-full rounded-full bg-cyan-400"
                          : "h-full rounded-full bg-gradient-to-r from-emerald-400 via-amber-300 to-rose-400"
                      }
                      style={{ width: `${metricWidth(metric)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>

      {contextMenu ? (
        <div
          className="border-border/80 bg-background fixed z-50 min-w-56 rounded-md border p-1 shadow-[0_18px_48px_rgba(0,0,0,0.4)]"
          style={{
            left: contextMenu.x,
            top: contextMenu.y,
          }}
        >
          <button
            type="button"
            className="hover:bg-accent hover:text-accent-foreground flex w-full flex-col rounded-sm px-3 py-2 text-left"
            onClick={() => openSensorDeck(contextMenu.metric)}
          >
            <span className="text-sm font-medium">Open In Sensor Deck</span>
            <span className="text-muted-foreground text-[0.7rem]">
              Set a constant value or drive {contextMenu.metric.signalLabel}{" "}
              with a function.
            </span>
          </button>
        </div>
      ) : null}
    </div>
  );
}
