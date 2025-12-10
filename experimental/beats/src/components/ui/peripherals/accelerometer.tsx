import { useSpecificPeripheralEvents } from "@/actions/ws/providers/PeripheralEventsProvider";
import React from "react";

type AccelData = {
  x: number;
  y: number;
  z: number;
};

type PeripheralTag = {
  name: string;
  variant: string;
  metadata?: Record<string, string>;
};

type PeripheralInfo = {
  id?: string | null;
  tags: PeripheralTag[];
};

type Props = {
  peripheral: PeripheralInfo;
  className?: string;
};

function formatNumber(n: number, digits = 2) {
  return Number.isFinite(n) ? n.toFixed(digits) : String(n);
}

export const AccelerometerView: React.FC<Props> = ({
  peripheral,
  className,
}) => {
  const events = useSpecificPeripheralEvents(peripheral.id ?? "unknown");

  if (!events || events.length === 0) {
    return (
      <div
        className={
          "flex flex-col gap-3 rounded-2xl border border-border bg-background/60 p-3 text-xs text-foreground shadow-sm " +
          (className ?? "")
        }
      >
        <span className="font-mono text-[0.7rem] uppercase tracking-wide text-muted-foreground">
          Acceleration
        </span>
        <p className="text-[0.7rem] text-muted-foreground font-mono">
          No acceleration events yet for {peripheral.id ?? "accelerometer"}.
        </p>
      </div>
    );
  }

  const latest = events[0].msg.payload as { data: AccelData };
  const acc = latest.data ?? { x: 0, y: 0, z: 0 };

  const mag = Math.sqrt(acc.x * acc.x + acc.y * acc.y + acc.z * acc.z);

  // Determine scaling range from data (keep a minimum so bars are visible)
  const maxAbs = Math.max(
    Math.abs(acc.x),
    Math.abs(acc.y),
    Math.abs(acc.z),
    0.1
  );
  
  // “Forgiving” range: don’t let it go below 1, but otherwise follow the max
  const range = maxAbs < 1 ? 1 : maxAbs;

  const axes: { key: keyof AccelData; label: string; colorClass: string }[] = [
    { key: "x", label: "X", colorClass: "text-red-500" },
    { key: "y", label: "Y", colorClass: "text-green-500" },
    { key: "z", label: "Z", colorClass: "text-blue-500" },
  ];

  return (
    <div
      className={
        "flex flex-col gap-3 rounded-2xl border border-border bg-background/60 p-3 text-xs text-foreground shadow-sm " +
        (className ?? "")
      }
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex flex-col">
          <span className="font-mono text-[0.7rem] uppercase tracking-wide text-muted-foreground">
            Acceleration
          </span>
          <span className="font-mono text-sm">
            {peripheral.id ?? "accelerometer"}
          </span>
        </div>
        <div className="flex flex-col items-end text-[0.7rem] font-mono text-muted-foreground">
          <span>
            |a|:{" "}
            <span className="text-foreground">
              {formatNumber(mag)} m/s²
            </span>
          </span>
          <span className="text-muted-foreground">
            range ±{formatNumber(range)} m/s²
          </span>
        </div>
      </div>

      <div className="flex gap-3">
        {/* Bars visualization */}
        <div className="relative w-2/3 min-w-[220px] rounded-xl border border-border bg-muted/40 px-2 py-3">
          <svg viewBox="0 0 120 60" className="h-full w-full">
            {/* center vertical line */}
            <line
              x1={60}
              y1={5}
              x2={60}
              y2={55}
              stroke="currentColor"
              strokeWidth={0.3}
              className="text-border/80"
              strokeDasharray="1 2"
            />
            {/* rows: X, Y, Z */}
            {axes.map((axis, idx) => {
              const value = acc[axis.key];
              const centerX = 60;
              const rowY = 15 + idx * 15; // 15, 30, 45
              const maxBarHalf = 50; // max half width
                // Raw ratio of this axis vs range
              const rawRatio = Math.abs(value) / range;

            // Eased scaling: sqrt makes small values more visible,
            // while big values still reach near full bar length.
            const easedRatio = Math.sqrt(Math.min(rawRatio, 1));

            // Final length in SVG units
            const barLength = easedRatio * maxBarHalf;

            // Keep a tiny minimum so non-zero values never look like a dot
            const finalLength = value === 0 ? 0 : Math.max(barLength, 6);

            const isPositive = value >= 0;
            const barX =
            centerX + (isPositive ? 0 : -finalLength); // start left or right of center

              return (
                <g key={axis.key} className="p-4">
                  {/* axis label */}
                  <text
                    x={5}
                    y={rowY + 1}
                    fontSize={4}
                    className="fill-muted-foreground font-mono"
                  >
                    {axis.label}
                  </text>

                  {/* 0-line label */}
                  {idx === 0 && (
                    <text
                      x={centerX + 1}
                      y={8}
                      fontSize={3}
                      className="fill-muted-foreground font-mono"
                    >
                      0
                    </text>
                  )}

                  {/* bar */}
                  <rect
                    x={barX}
                    y={rowY - 4}
                    width={finalLength || 0.5}
                    height={8}
                    rx={2}
                    fill="currentColor"
                    className={axis.colorClass}
                  />

                  {/* numeric value */}
                  <text
                    x={centerX + maxBarHalf}
                    y={rowY + 1}
                    fontSize={3.5}
                    className="fill-foreground font-mono"
                  >
                    {formatNumber(value)}
                  </text>
                </g>
              );
            })}
          </svg>

          <div className="pointer-events-none absolute inset-x-0 bottom-1 flex select-none justify-center text-[0.6rem] font-mono text-muted-foreground">
            <span>Negative &larr; X axis &rarr; Positive (per row)</span>
          </div>
        </div>

        {/* Details panel */}
        <div className="flex-1 space-y-2">
          <div className="rounded-lg border border-border/70 bg-background/80 p-2 font-mono text-[0.7rem]">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-muted-foreground">Components (m/s²)</span>
            </div>
            <div className="grid grid-cols-3 gap-1">
              <div>
                <div className="text-muted-foreground">x</div>
                <div className="text-foreground">
                  {formatNumber(acc.x)}
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">y</div>
                <div className="text-foreground">
                  {formatNumber(acc.y)}
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">z</div>
                <div className="text-foreground">
                  {formatNumber(acc.z)}
                </div>
              </div>
            </div>
          </div>

          <p className="text-[0.6rem] font-mono text-muted-foreground">
            Each row shows acceleration along one axis, centered at 0. Bar
            length encodes magnitude; side encodes sign.
          </p>
        </div>
      </div>
    </div>
  );
};