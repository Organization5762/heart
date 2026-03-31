import { useSpecificPeripheralEvents } from "@/actions/ws/providers/PeripheralEventsProvider";
import { PeripheralInfo } from "@/actions/ws/providers/PeripheralProvider";
import React from "react";

type SwitchState = {
  rotational_value: number;
  button_value: number;
  long_button_value: number;
  rotation_since_last_button_press: number;
  rotation_since_last_long_button_press: number;
};

type Props = {
  peripheral: PeripheralInfo;
  className?: string;
};

function formatNumber(n: number, digits = 0) {
  return Number.isFinite(n) ? n.toFixed(digits) : String(n);
}

function clamp(v: number, min: number, max: number) {
  return Math.min(max, Math.max(min, v));
}

export const RotarySwitchView: React.FC<Props> = ({
  peripheral,
  className,
}) => {
  const events = useSpecificPeripheralEvents(peripheral.id ?? "unknown");

  if (!events || events.length === 0) {
    return (
      <div
        className={
          "border-border bg-background/60 text-foreground flex flex-col gap-3 border p-3 text-xs " +
          (className ?? "")
        }
      >
        <span className="text-muted-foreground font-mono text-[0.7rem] tracking-wide uppercase">
          Rotary Switch
        </span>
        <p className="text-muted-foreground font-mono text-[0.7rem]">
          No switch events yet for {peripheral.id ?? "rotary_switch"}.
        </p>
      </div>
    );
  }

  const latest = events[0].msg.payload as { data: SwitchState };
  const state: SwitchState = latest.data;

  // --- Rotary geometry -------------------------------------------------------

  const STEPS_PER_REV = 24; // feel free to tune if your encoder differs

  const normalizedStep =
    ((state.rotational_value % STEPS_PER_REV) + STEPS_PER_REV) % STEPS_PER_REV;

  const angleDeg = normalizedStep * (360 / STEPS_PER_REV) - 90; // 0 at top
  const angleRad = (angleDeg * Math.PI) / 180;

  const centerX = 50;
  const centerY = 50;
  const needleRadius = 25;

  const needleX = centerX + Math.cos(angleRad) * needleRadius;
  const needleY = centerY + Math.sin(angleRad) * needleRadius;

  // --- History rings (since last presses) -----------------------------------

  const shortDelta = state.rotation_since_last_button_press;
  const longDelta = state.rotation_since_last_long_button_press;

  const maxSpan = Math.max(
    Math.abs(shortDelta),
    Math.abs(longDelta),
    4, // minimum span so small moves are still visible
  );

  const shortRatio = clamp(Math.abs(shortDelta) / maxSpan, 0, 1);
  const longRatio = clamp(Math.abs(longDelta) / maxSpan, 0, 1);

  const shortRadius = 34;
  const longRadius = 38;
  const shortCirc = 2 * Math.PI * shortRadius;
  const longCirc = 2 * Math.PI * longRadius;

  const shortLength = shortCirc * shortRatio;
  const longLength = longCirc * longRatio;

  // start arcs at top (-90deg) by offsetting half a circumference
  const baseOffsetShort = shortCirc * 0.25;
  const baseOffsetLong = longCirc * 0.25;

  const shortOffset = baseOffsetShort;
  const longOffset = baseOffsetLong;

  const prevPayload = events[1]?.msg.payload as
    | { data: SwitchState }
    | undefined;
  const prevState = prevPayload?.data;

  // how many presses happened since last event
  const buttonDelta =
    prevState != null
      ? Math.max(0, state.button_value - prevState.button_value)
      : 0;

  const longButtonDelta =
    prevState != null
      ? Math.max(0, state.long_button_value - prevState.long_button_value)
      : 0;

  // "pressed" now means "we saw at least one new press in this frame"
  const buttonPressed = buttonDelta > 0;
  const longPressed = longButtonDelta > 0;

  return (
    <div
      className={
        "border-border bg-background/60 text-foreground flex flex-col gap-3 border p-3 text-xs " +
        (className ?? "")
      }
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex flex-col">
          <span className="text-muted-foreground font-mono text-[0.7rem] tracking-wide uppercase">
            Rotary Switch
          </span>
          <span className="font-mono text-sm">
            {peripheral.id ?? "rotary_switch"}
          </span>
        </div>

        <div className="text-muted-foreground flex flex-col items-end gap-1 font-mono text-[0.7rem]">
          <span>
            step:{" "}
            <span className="text-foreground">
              {formatNumber(normalizedStep)}
            </span>
            <span className="text-muted-foreground"> / {STEPS_PER_REV}</span>
          </span>
          <span>
            total:{" "}
            <span className="text-foreground">
              {formatNumber(state.rotational_value)}
            </span>
          </span>
        </div>
      </div>

      <div className="flex gap-3">
        {/* Dial */}
        <div className="border-border bg-muted/40 relative aspect-square w-2/3 min-w-[220px] border">
          <svg viewBox="0 0 100 100" className="h-full w-full">
            {/* dial background */}
            <circle
              cx={centerX}
              cy={centerY}
              r={30}
              fill="currentColor"
              className="text-background"
              stroke="currentColor"
              strokeWidth={0.5}
              strokeOpacity={0.5}
            />

            {/* ticks */}
            {Array.from({ length: STEPS_PER_REV }).map((_, i) => {
              const stepAngle =
                ((i / STEPS_PER_REV) * 360 - 90) * (Math.PI / 180);
              const outerR = 30;
              const innerR = i % 4 === 0 ? 24 : 27;
              const ox = centerX + Math.cos(stepAngle) * outerR;
              const oy = centerY + Math.sin(stepAngle) * outerR;
              const ix = centerX + Math.cos(stepAngle) * innerR;
              const iy = centerY + Math.sin(stepAngle) * innerR;
              return (
                <line
                  key={i}
                  x1={ix}
                  y1={iy}
                  x2={ox}
                  y2={oy}
                  stroke="currentColor"
                  strokeWidth={i % 4 === 0 ? 0.9 : 0.4}
                  className="text-border/80"
                />
              );
            })}

            {/* history rings */}
            {/* short press ring */}
            <circle
              cx={centerX}
              cy={centerY}
              r={shortRadius}
              fill="none"
              stroke="currentColor"
              strokeWidth={1.2}
              className="text-emerald-400"
              strokeDasharray={`${shortLength} ${shortCirc}`}
              strokeDashoffset={shortOffset}
              strokeLinecap="round"
            />
            {/* long press ring */}
            <circle
              cx={centerX}
              cy={centerY}
              r={longRadius}
              fill="none"
              stroke="currentColor"
              strokeWidth={1.2}
              className="text-indigo-400"
              strokeDasharray={`${longLength} ${longCirc}`}
              strokeDashoffset={longOffset}
              strokeLinecap="round"
            />

            {/* needle */}
            <line
              x1={centerX}
              y1={centerY}
              x2={needleX}
              y2={needleY}
              stroke="currentColor"
              strokeWidth={2}
              className="text-foreground"
              strokeLinecap="round"
            />
            <circle
              cx={centerX}
              cy={centerY}
              r={3}
              fill="currentColor"
              className="text-foreground"
            />

            {/* center label */}
            <text
              x={centerX}
              y={centerY + 15}
              fontSize={4}
              textAnchor="middle"
              className="fill-muted-foreground font-mono"
            >
              step {formatNumber(normalizedStep)}/{STEPS_PER_REV}
            </text>
          </svg>

          {/* legend labels on the dial */}
          <div className="text-muted-foreground pointer-events-none absolute inset-0 flex flex-col justify-between p-1 font-mono text-[0.6rem]">
            <div className="mt-1 flex justify-center gap-3">
              <span className="flex items-center gap-1">
                <span className="inline-block h-[6px] w-[6px] rounded-full bg-emerald-400" />
                since short press
              </span>
              <span className="flex items-center gap-1">
                <span className="inline-block h-[6px] w-[6px] rounded-full bg-indigo-400" />
                since long press
              </span>
            </div>
            <div className="mb-1 flex justify-center">
              <span>Dial orientation follows rotational_value</span>
            </div>
          </div>
        </div>

        {/* Right side: button states & deltas */}
        <div className="flex-1 space-y-2">
          {/* button state */}
          <div className="border-border/70 bg-background/80 space-y-2 border p-2 font-mono text-[0.7rem]">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">Buttons</span>
            </div>
            <div className="flex flex-col gap-1">
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">short</span>
                <span
                  className={
                    "rounded-full px-2 py-[1px] text-[0.65rem] tracking-wide uppercase " +
                    (buttonPressed
                      ? "border border-emerald-500/40 bg-emerald-500/10 text-emerald-500"
                      : "bg-muted text-muted-foreground border-border/70 border")
                  }
                >
                  {buttonPressed ? `Pressed ×${buttonDelta}` : "No new press"}
                </span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-muted-foreground">long</span>
                <span
                  className={
                    "rounded-full px-2 py-[1px] text-[0.65rem] tracking-wide uppercase " +
                    (longPressed
                      ? "border border-indigo-500/40 bg-indigo-500/10 text-indigo-500"
                      : "bg-muted text-muted-foreground border-border/70 border")
                  }
                >
                  {longPressed ? `Pressed ×${longButtonDelta}` : "No new press"}
                </span>
              </div>
            </div>
          </div>

          {/* rotation since presses */}
          <div className="border-border/70 bg-background/80 space-y-2 border p-2 font-mono text-[0.7rem]">
            <div className="flex items-center justify-between">
              <span className="text-muted-foreground">
                Rotation since press
              </span>
              <span className="text-muted-foreground">steps</span>
            </div>
            <div className="space-y-1">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1">
                  <span className="inline-block h-[6px] w-[6px] rounded-full bg-emerald-400" />
                  <span className="text-muted-foreground">short</span>
                </div>
                <span
                  className={
                    "text-foreground " +
                    (shortDelta !== 0
                      ? "font-semibold"
                      : "text-muted-foreground")
                  }
                >
                  {shortDelta > 0 ? "+" : ""}
                  {formatNumber(shortDelta)}
                </span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1">
                  <span className="inline-block h-[6px] w-[6px] rounded-full bg-indigo-400" />
                  <span className="text-muted-foreground">long</span>
                </div>
                <span
                  className={
                    "text-foreground " +
                    (longDelta !== 0
                      ? "font-semibold"
                      : "text-muted-foreground")
                  }
                >
                  {longDelta > 0 ? "+" : ""}
                  {formatNumber(longDelta)}
                </span>
              </div>
            </div>
          </div>

          <p className="text-muted-foreground font-mono text-[0.6rem]">
            Needle shows current rotary position. Coloured rings encode how far
            you&apos;ve rotated since the last short and long button presses.
          </p>
        </div>
      </div>
    </div>
  );
};
