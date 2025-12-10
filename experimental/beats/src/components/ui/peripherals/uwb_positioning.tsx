import { useSpecificPeripheralEvents } from "@/actions/ws/providers/PeripheralEventsProvider";
import React, { useState } from "react";

type Station = {
  distance: number;
  station_id: string;
  x: number;
  y: number;
  z: number;
};

type UWBData = {
  stations: Station[];
  x: number; // target x
  y: number; // target y
  z: number; // target z
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

type UWBPositioningPayload = {
  data: UWBData;
  peripheral_info: PeripheralInfo;
};

type Props = {
  peripheral: PeripheralInfo;
  className?: string;
};

type Point2D = {
  u: number;
  v: number;
};

type Plane = "xy" | "xz" | "yz";

type NormalizedStation = Station & {
  sx: number;
  sy: number;
};

function normalizePoints(
  stations: Station[],
  target: Point2D,
  paddingPercent = 10
) {
  const us = [...stations.map((s) => s.u), target.u];
  const vs = [...stations.map((s) => s.v), target.v];

  const minU = Math.min(...us);
  const maxU = Math.max(...us);
  const minV = Math.min(...vs);
  const maxV = Math.max(...vs);

  const spanU = maxU - minU || 1;
  const spanV = maxV - minV || 1;

  const innerMin = paddingPercent;
  const innerMax = 100 - paddingPercent;

  const scaleU = (u: number) =>
    innerMin + ((u - minU) / spanU) * (innerMax - innerMin);
  const scaleV = (v: number) =>
    // Flip so “up” in coords is “up” on screen
    innerMax - ((v - minV) / spanV) * (innerMax - innerMin);

  return {
    stations: stations.map((s: Station & { u: number; v: number }) => ({
      ...s,
      sx: scaleU(s.u),
      sy: scaleV(s.v),
    })) as NormalizedStation[],
    target: {
      sx: scaleU(target.u),
      sy: scaleV(target.v),
    },
  };
}

function formatNumber(n: number, digits = 2) {
  return Number.isFinite(n) ? n.toFixed(digits) : String(n);
}

function projectStation(station: Station, plane: Plane): { u: number; v: number } {
  switch (plane) {
    case "xy":
      return { u: station.x, v: station.y };
    case "xz":
      return { u: station.x, v: station.z };
    case "yz":
      return { u: station.y, v: station.z };
  }
}

function projectTarget(target: { x: number; y: number; z: number }, plane: Plane) {
  switch (plane) {
    case "xy":
      return { u: target.x, v: target.y };
    case "xz":
      return { u: target.x, v: target.z };
    case "yz":
      return { u: target.y, v: target.z };
  }
}

function planeAxisLabels(plane: Plane): { uLabel: string; vLabel: string } {
  switch (plane) {
    case "xy":
      return { uLabel: "X axis", vLabel: "Y axis" };
    case "xz":
      return { uLabel: "X axis", vLabel: "Z axis" };
    case "yz":
      return { uLabel: "Y axis", vLabel: "Z axis" };
  }
}

export const UWBPositionView: React.FC<Props> = ({ peripheral, className }) => {
  const events = useSpecificPeripheralEvents(peripheral.id ?? "unknown");
  const [plane, setPlane] = useState<Plane>("xy");

  if (!events || events.length === 0) {
    return (
      <div
        className={
          "flex flex-col gap-3 rounded-2xl border border-border bg-background/60 p-3 text-xs text-foreground shadow-sm " +
          (className ?? "")
        }
      >
        <span className="font-mono text-[0.7rem] uppercase tracking-wide text-muted-foreground">
          UWB Positioning
        </span>
        <p className="text-[0.7rem] text-muted-foreground font-mono">
          No UWB events yet for {peripheral.id ?? "uwb_peripheral"}.
        </p>
      </div>
    );
  }

  const latest = events[0].msg.payload as UWBPositioningPayload;
  const data = latest.data;
  const worldTarget = { x: data.x, y: data.y, z: data.z };

  // Project to the chosen plane
  const projectedStations = data.stations.map((s) => {
    const { u, v } = projectStation(s, plane);
    return { ...s, u, v };
  });
  const projectedTarget = projectTarget(worldTarget, plane);

  const { stations: normStations, target } = normalizePoints(
    projectedStations,
    projectedTarget
  );

  const { uLabel, vLabel } = planeAxisLabels(plane);

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
            UWB Positioning
          </span>
          <span className="font-mono text-sm">
            {peripheral.id ?? "uwb_peripheral"}
          </span>
        </div>

        <div className="flex flex-col items-end gap-1 text-[0.7rem] font-mono text-muted-foreground">
          <span>{peripheral.id ?? "uwb_peripheral"}</span>
          {/* Plane selector */}
          <div className="inline-flex rounded-md border border-border bg-background/80 overflow-hidden">
            {(["xy", "xz", "yz"] as Plane[]).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setPlane(p)}
                className={
                  "px-2 py-[2px] text-[0.65rem] uppercase tracking-wide " +
                  (plane === p
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:bg-muted/60")
                }
              >
                {p.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex gap-3">
        {/* SVG / Map */}
        <div className="relative aspect-square w-2/3 min-w-[220px] rounded-xl border border-border bg-muted/40">
          <svg viewBox="0 0 100 100" className="h-full w-full">
            {/* Grid */}
            {[20, 40, 60, 80].map((val) => (
              <React.Fragment key={val}>
                <line
                  x1={val}
                  y1={5}
                  x2={val}
                  y2={95}
                  stroke="currentColor"
                  strokeWidth={0.2}
                  className="text-border/60"
                  strokeDasharray="1 2"
                />
                <line
                  x1={5}
                  y1={val}
                  x2={95}
                  y2={val}
                  stroke="currentColor"
                  strokeWidth={0.2}
                  className="text-border/60"
                  strokeDasharray="1 2"
                />
              </React.Fragment>
            ))}

            {/* Bounding box */}
            <rect
              x={8}
              y={8}
              width={84}
              height={84}
              fill="none"
              stroke="currentColor"
              strokeWidth={0.6}
              className="text-border"
            />

            {/* Base stations */}
            {normStations.map((s) => (
              <g key={s.station_id}>
                <rect
                  x={s.sx - 2.5}
                  y={s.sy - 2.5}
                  width={5}
                  height={5}
                  rx={0.7}
                  fill="currentColor"
                  className="text-blue-500"
                />
                <text
                  x={s.sx + 3}
                  y={s.sy - 3}
                  fontSize={3}
                  className="fill-foreground"
                >
                  {s.station_id}
                </text>
              </g>
            ))}

            {/* Target */}
            <g>
              <circle
                cx={target.sx}
                cy={target.sy}
                r={2}
                fill="none"
                stroke="currentColor"
                strokeWidth={0.8}
                className="text-emerald-500"
              />
              <circle
                cx={target.sx}
                cy={target.sy}
                r={2}
                fill="currentColor"
                className="text-emerald-500"
              />
              <text
                x={target.sx + 2 + 1}
                y={target.sy + 3}
                fontSize={3}
                className="fill-foreground"
              >
                target
              </text>
            </g>
          </svg>

          {/* Axes labels */}
          <div className="pointer-events-none absolute inset-0 flex select-none items-start justify-between p-1 text-[0.6rem] font-mono text-muted-foreground">
            <span>{uLabel}</span>
            <span>{vLabel}</span>
          </div>
        </div>

        {/* Details panel */}
        <div className="flex-1 space-y-2">
          <div className="rounded-lg border border-border/70 bg-background/80 p-2 font-mono text-[0.7rem]">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-muted-foreground">Target (solved)</span>
            </div>
            <div className="grid grid-cols-3 gap-1">
              <div>
                <div className="text-muted-foreground">x</div>
                <div className="text-foreground">
                  {formatNumber(worldTarget.x)}
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">y</div>
                <div className="text-foreground">
                  {formatNumber(worldTarget.y)}
                </div>
              </div>
              <div>
                <div className="text-muted-foreground">z</div>
                <div className="text-foreground">
                  {formatNumber(worldTarget.z)}
                </div>
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-border/70 bg-background/80 p-2 font-mono text-[0.7rem]">
            <div className="mb-1 flex items-center justify-between">
              <span className="text-muted-foreground">Base stations</span>
              <span className="text-muted-foreground">dist (m)</span>
            </div>
            <div className="space-y-1 max-h-40 overflow-auto pr-1">
              {normStations.map((s) => (
                <div
                  key={s.station_id}
                  className="flex items-baseline justify-between gap-2 rounded-md px-1 py-0.5 hover:bg-muted/60"
                >
                  <div className="flex flex-col">
                    <span className="text-foreground">{s.station_id}</span>
                    <span className="text-muted-foreground">
                      ({formatNumber(s.x)}, {formatNumber(s.y)},{" "}
                      {formatNumber(s.z)})
                    </span>
                  </div>
                  <span className="text-foreground">
                    {formatNumber(s.distance, 3)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          <p className="text-[0.6rem] font-mono text-muted-foreground">
            {plane.toUpperCase()} projection. Distances are measured from each
            base station to the target.
          </p>
        </div>
      </div>
    </div>
  );
};
