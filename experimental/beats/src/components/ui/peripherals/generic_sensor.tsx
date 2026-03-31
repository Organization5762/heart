import type { PeripheralInfo } from "@/actions/ws/providers/PeripheralProvider";

type PreviewMetric = {
  id: string;
  label: string;
  kind: "numeric" | "boolean";
  value: number | boolean;
};

const MAX_PREVIEW_METRICS = 6;

export function collectPreviewMetrics(payload: unknown): PreviewMetric[] {
  const metrics: PreviewMetric[] = [];

  function visit(value: unknown, path: string[]) {
    if (metrics.length >= MAX_PREVIEW_METRICS) {
      return;
    }

    if (typeof value === "number" && Number.isFinite(value)) {
      metrics.push({
        id: path.join("."),
        label: path.join("."),
        kind: "numeric",
        value,
      });
      return;
    }

    if (typeof value === "boolean") {
      metrics.push({
        id: path.join("."),
        label: path.join("."),
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
  const metrics = collectPreviewMetrics(lastData);

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
        "border-border bg-background/60 text-foreground flex flex-col gap-3 border p-3 text-xs " +
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

      <div className="grid gap-2">
        {metrics.map((metric) => (
          <div
            key={metric.id}
            className="border-border/70 bg-background/80 rounded-sm border px-3 py-2"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-muted-foreground truncate font-mono text-[0.68rem] uppercase">
                {metric.label}
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
    </div>
  );
}
