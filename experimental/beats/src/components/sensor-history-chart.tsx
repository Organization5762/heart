import type { SensorHistoryPoint } from "@/features/stream-console/sensor-simulation";

const CHART_HEIGHT = 220;
const CHART_WIDTH = 720;
const DEFAULT_WINDOW_SECONDS = 30;

type ChartLine = {
  color: string;
  key: "effectiveValue" | "liveValue" | "referenceValue";
  label: string;
};

const CHART_LINES: ChartLine[] = [
  {
    color: "#34d399",
    key: "effectiveValue",
    label: "Applied",
  },
  {
    color: "#e2e8f0",
    key: "liveValue",
    label: "Live",
  },
  {
    color: "#f59e0b",
    key: "referenceValue",
    label: "Function",
  },
];

export function SensorHistoryChart({
  points,
  windowSeconds = DEFAULT_WINDOW_SECONDS,
}: {
  points: SensorHistoryPoint[];
  windowSeconds?: number;
}) {
  if (points.length === 0) {
    return (
      <div className="flex h-[220px] items-center justify-center rounded-xl border border-dashed border-[#404754] bg-[#0b0f14] text-sm text-[#95a2b6]">
        History will appear after the first sensor samples are collected.
      </div>
    );
  }

  const endTime = points[points.length - 1]?.timeSeconds ?? 0;
  const startTime = Math.max(0, endTime - windowSeconds);
  const visiblePoints = points.filter(
    (point) => point.timeSeconds >= startTime,
  );
  const domain = computeDomain(visiblePoints);
  const hasFunctionSeries = visiblePoints.some(
    (point) => point.referenceValue !== null,
  );

  return (
    <div className="rounded-xl border border-[#404754] bg-[#0b0f14] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-tomorrow text-[10px] tracking-[0.22em] text-[#738194] uppercase">
            Sensor Trace
          </p>
          <h3 className="font-tomorrow text-sm tracking-[0.12em] text-slate-100 uppercase">
            Last {windowSeconds}s
          </h3>
        </div>
        <div className="flex flex-wrap gap-3 text-[11px] tracking-[0.16em] text-[#8d9bb0] uppercase">
          {CHART_LINES.filter(
            (line) => hasFunctionSeries || line.key !== "referenceValue",
          ).map((line) => (
            <span key={line.key} className="flex items-center gap-2">
              <span
                className="h-2.5 w-2.5 rounded-full"
                style={{ backgroundColor: line.color }}
              />
              {line.label}
            </span>
          ))}
        </div>
      </div>

      <div className="relative">
        <svg
          viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
          className="h-[220px] w-full rounded-lg bg-slate-950/80"
          role="img"
          aria-label="Sensor history chart"
        >
          {Array.from({ length: 5 }).map((_, index) => {
            const y = (index / 4) * CHART_HEIGHT;
            return (
              <line
                key={`h-${index}`}
                x1={0}
                y1={y}
                x2={CHART_WIDTH}
                y2={y}
                stroke="rgba(148, 163, 184, 0.16)"
                strokeWidth={1}
              />
            );
          })}
          {Array.from({ length: 7 }).map((_, index) => {
            const x = (index / 6) * CHART_WIDTH;
            return (
              <line
                key={`v-${index}`}
                x1={x}
                y1={0}
                x2={x}
                y2={CHART_HEIGHT}
                stroke="rgba(148, 163, 184, 0.12)"
                strokeWidth={1}
              />
            );
          })}

          {CHART_LINES.filter(
            (line) => hasFunctionSeries || line.key !== "referenceValue",
          ).map((line) => {
            const polylinePoints = toPolylinePoints(
              visiblePoints,
              line.key,
              startTime,
              endTime,
              domain,
            );
            if (!polylinePoints) {
              return null;
            }

            return (
              <polyline
                key={line.key}
                fill="none"
                points={polylinePoints}
                stroke={line.color}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={line.key === "effectiveValue" ? 3 : 2}
              />
            );
          })}
        </svg>

        <div className="pointer-events-none absolute inset-x-0 top-0 flex justify-between px-2 pt-2 text-[10px] tracking-[0.14em] text-slate-300 uppercase">
          <span>{domain.max.toFixed(2)}</span>
          <span>Now</span>
        </div>
        <div className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-between px-2 pb-2 text-[10px] tracking-[0.14em] text-slate-400 uppercase">
          <span>{domain.min.toFixed(2)}</span>
          <span>{startTime.toFixed(0)}s</span>
        </div>
      </div>
    </div>
  );
}

function computeDomain(points: SensorHistoryPoint[]) {
  const values = points.flatMap((point) => [
    point.liveValue,
    point.effectiveValue,
    point.referenceValue,
  ]);
  const numericValues = values.filter(
    (value): value is number =>
      typeof value === "number" && Number.isFinite(value),
  );

  if (numericValues.length === 0) {
    return { min: -1, max: 1 };
  }

  let min = Math.min(...numericValues);
  let max = Math.max(...numericValues);

  if (min === max) {
    min -= 1;
    max += 1;
  }

  const padding = (max - min) * 0.1;
  return {
    min: min - padding,
    max: max + padding,
  };
}

function toPolylinePoints(
  points: SensorHistoryPoint[],
  key: ChartLine["key"],
  startTime: number,
  endTime: number,
  domain: { min: number; max: number },
) {
  const samples = points.flatMap((point) => {
    const value = point[key];
    if (value === null || !Number.isFinite(value)) {
      return [];
    }

    return [
      `${scaleX(point.timeSeconds, startTime, endTime)},${scaleY(
        value,
        domain.min,
        domain.max,
      )}`,
    ];
  });

  if (samples.length === 0) {
    return null;
  }

  if (samples.length === 1) {
    return `${samples[0]} ${samples[0]}`;
  }

  return samples.join(" ");
}

function scaleX(value: number, min: number, max: number) {
  if (max <= min) {
    return CHART_WIDTH;
  }
  return ((value - min) / (max - min)) * CHART_WIDTH;
}

function scaleY(value: number, min: number, max: number) {
  if (max <= min) {
    return CHART_HEIGHT / 2;
  }
  return CHART_HEIGHT - ((value - min) / (max - min)) * CHART_HEIGHT;
}
