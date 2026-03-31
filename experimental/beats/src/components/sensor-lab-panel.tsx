import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SensorHistoryChart } from "@/components/sensor-history-chart";
import {
  SENSOR_FUNCTION_PRESETS,
  defaultSensorOverride,
  formatSensorValue,
  type ResolvedSensorChannel,
  type SensorHistoryPoint,
  type SensorOverride,
} from "@/features/stream-console/sensor-simulation";
import { Activity, Gauge, ScanLine, SlidersHorizontal } from "lucide-react";

export function SensorLabPanel({
  clockSeconds,
  onClearHistory,
  onResetOverride,
  onSelectSensor,
  onUpdateOverride,
  override,
  selectedSensor,
  selectedSensorHistory,
  sensors,
}: {
  clockSeconds: number;
  onClearHistory: () => void;
  onResetOverride: (sensorId: string) => void;
  onSelectSensor: (sensorId: string) => void;
  onUpdateOverride: (sensorId: string, patch: Partial<SensorOverride>) => void;
  override: SensorOverride;
  selectedSensor: ResolvedSensorChannel | null;
  selectedSensorHistory: SensorHistoryPoint[];
  sensors: ResolvedSensorChannel[];
}) {
  return (
    <section className="rounded-[1.5rem] border border-[#2f353f] bg-[linear-gradient(180deg,_rgba(29,33,40,0.96),_rgba(14,17,23,0.98))] p-4 shadow-[0_24px_60px_rgba(0,0,0,0.45)]">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-tomorrow text-[11px] tracking-[0.22em] text-[#7f8ea3] uppercase">
            Sensor Rack
          </p>
          <h2 className="font-tomorrow text-lg tracking-[0.14em] text-slate-100 uppercase">
            Mocking and Trace Console
          </h2>
          <p className="text-sm text-[#a4b0c2]">
            Compare live values, applied overrides, and time-driven functions in
            one panel.
          </p>
        </div>
        <div className="rounded-xl border border-[#3a414c] bg-[#0b0f14] px-3 py-2 text-right shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
          <div className="font-tomorrow text-[10px] tracking-[0.2em] text-[#738194] uppercase">
            Simulation Clock
          </div>
          <div className="font-mono text-xl text-[#e3edf7]">
            {clockSeconds.toFixed(1)}s
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)]">
        <div className="space-y-3">
          <div className="rounded-xl border border-[#3a414c] bg-[#10141a] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
            <div className="mb-3 flex items-center gap-2">
              <Activity className="h-4 w-4 text-emerald-500" />
              <h3 className="font-tomorrow text-sm tracking-[0.12em] text-slate-100 uppercase">
                Detected Sensors
              </h3>
            </div>
            <div className="space-y-2">
              {sensors.map((sensor) => (
                <button
                  key={sensor.id}
                  type="button"
                  onClick={() => onSelectSensor(sensor.id)}
                  className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                    selectedSensor?.id === sensor.id
                      ? "border-[#5b8cff] bg-[#162235] shadow-[inset_0_0_0_1px_rgba(91,140,255,0.2)]"
                      : "border-[#3a414c] bg-[#181d24] hover:bg-[#1d232c]"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-medium text-slate-100">
                      {sensor.label}
                    </span>
                    <span className="font-tomorrow rounded-full border border-[#464e5b] px-2 py-0.5 text-[10px] tracking-[0.16em] text-[#96a3b7] uppercase">
                      {sensor.source}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center justify-between gap-3 text-xs text-[#95a2b6]">
                    <span>Live {sensor.displayValue}</span>
                    <span>
                      Applied {formatSensorValue(sensor.effectiveValue, 2)}
                    </span>
                  </div>
                  <div className="mt-3 h-2 overflow-hidden rounded-full bg-[#0d1116]">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-emerald-400 via-amber-300 to-rose-400"
                      style={{
                        width: `${Math.max(
                          8,
                          Math.round(
                            Math.abs(Math.tanh(sensor.effectiveValue)) * 100,
                          ),
                        )}%`,
                      }}
                    />
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="space-y-4">
          {selectedSensor ? (
            <>
              <div className="rounded-xl border border-[#3a414c] bg-[#10141a] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
                <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <Gauge className="h-4 w-4 text-sky-500" />
                      <h3 className="text-base font-semibold text-slate-100">
                        {selectedSensor.label}
                      </h3>
                    </div>
                    <p className="mt-1 text-sm text-[#9aa7ba]">
                      Path:{" "}
                      <span className="font-mono text-[#dfe8f5]">
                        {selectedSensor.path}
                      </span>
                    </p>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={onClearHistory}
                      className="border-[#404754] bg-[#171c23] text-slate-200 hover:bg-[#1f252d]"
                    >
                      Clear History
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => onResetOverride(selectedSensor.id)}
                      className="border-[#404754] bg-[#171c23] text-slate-200 hover:bg-[#1f252d]"
                    >
                      Reset Mock
                    </Button>
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                  <MetricTile
                    label="Live"
                    value={formatSensorValue(selectedSensor.value, 2)}
                    helper={selectedSensor.displayValue}
                  />
                  <MetricTile
                    label="Applied"
                    value={formatSensorValue(selectedSensor.effectiveValue, 2)}
                    helper={
                      override.mode === "live"
                        ? "Following hardware"
                        : override.mode === "constant"
                          ? "Pinned constant"
                          : "Function output"
                    }
                  />
                  <MetricTile
                    label="Reference"
                    value={formatSensorValue(selectedSensor.referenceValue, 2)}
                    helper={
                      selectedSensor.evaluationError
                        ? selectedSensor.evaluationError
                        : override.mode === "function"
                          ? "Function target"
                          : "No function"
                    }
                    accent={
                      selectedSensor.evaluationError
                        ? "text-amber-500"
                        : undefined
                    }
                  />
                </div>
              </div>

              <div className="rounded-xl border border-[#3a414c] bg-[#10141a] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
                <div className="mb-4 flex items-center gap-2">
                  <SlidersHorizontal className="h-4 w-4 text-violet-500" />
                  <h3 className="font-tomorrow text-sm tracking-[0.12em] text-slate-100 uppercase">
                    Mock Source
                  </h3>
                </div>
                <div className="mb-4 flex flex-wrap gap-2">
                  {(["live", "constant", "function"] as const).map((mode) => (
                    <Button
                      key={mode}
                      type="button"
                      size="sm"
                      variant={override.mode === mode ? "default" : "outline"}
                      onClick={() =>
                        onUpdateOverride(selectedSensor.id, { mode })
                      }
                      className={
                        override.mode === mode
                          ? "bg-[#3b82f6] text-white hover:bg-[#2563eb]"
                          : "border-[#404754] bg-[#171c23] text-slate-200 hover:bg-[#1f252d]"
                      }
                    >
                      {mode}
                    </Button>
                  ))}
                </div>

                {override.mode === "constant" ? (
                  <label className="block space-y-2">
                    <span className="font-tomorrow text-[10px] tracking-[0.2em] text-[#7f8ea3] uppercase">
                      Constant Value
                    </span>
                    <Input
                      type="number"
                      value={override.constantValue}
                      step="0.1"
                      className="border-[#404754] bg-[#0c1015] font-mono text-[#e3edf7]"
                      onChange={(event) =>
                        onUpdateOverride(selectedSensor.id, {
                          constantValue: Number(event.target.value),
                        })
                      }
                    />
                  </label>
                ) : null}

                {override.mode === "function" ? (
                  <div className="space-y-3">
                    <label className="block space-y-2">
                      <span className="font-tomorrow text-[10px] tracking-[0.2em] text-[#7f8ea3] uppercase">
                        Function of t (seconds)
                      </span>
                      <textarea
                        className="min-h-[96px] w-full rounded-md border border-[#404754] bg-[#0c1015] px-3 py-2 font-mono text-sm text-[#e3edf7] transition outline-none focus-visible:border-[#6f9fff] focus-visible:ring-2 focus-visible:ring-[#6f9fff]/30"
                        value={override.expression}
                        onChange={(event) =>
                          onUpdateOverride(selectedSensor.id, {
                            expression: event.target.value,
                          })
                        }
                      />
                    </label>
                    <div className="flex flex-wrap gap-2">
                      {SENSOR_FUNCTION_PRESETS.map((preset) => (
                        <Button
                          key={preset.label}
                          type="button"
                          size="sm"
                          variant="outline"
                          className="border-[#404754] bg-[#171c23] text-slate-200 hover:bg-[#1f252d]"
                          onClick={() =>
                            onUpdateOverride(selectedSensor.id, {
                              expression: preset.expression,
                            })
                          }
                        >
                          {preset.label}
                        </Button>
                      ))}
                    </div>
                    <div className="rounded-xl border border-[#404754] bg-[#171c23] p-3 text-xs text-[#95a2b6]">
                      Available helpers: <span className="font-mono">sin</span>,{" "}
                      <span className="font-mono">cos</span>,{" "}
                      <span className="font-mono">triangle</span>,{" "}
                      <span className="font-mono">pulse</span>,{" "}
                      <span className="font-mono">saw</span>,{" "}
                      <span className="font-mono">clamp</span>, and{" "}
                      <span className="font-mono">mix</span>.
                    </div>
                  </div>
                ) : null}

                {override.mode === "live" ? (
                  <div className="rounded-xl border border-[#404754] bg-[#171c23] p-3 text-sm text-[#95a2b6]">
                    Live mode forwards the latest connected peripheral value
                    without modification.
                  </div>
                ) : null}
              </div>

              <div className="rounded-xl border border-[#3a414c] bg-[#10141a] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
                <div className="mb-4 flex items-center gap-2">
                  <ScanLine className="h-4 w-4 text-amber-500" />
                  <h3 className="font-tomorrow text-sm tracking-[0.12em] text-slate-100 uppercase">
                    Observed vs Reference
                  </h3>
                </div>
                <SensorHistoryChart points={selectedSensorHistory} />
              </div>
            </>
          ) : (
            <div className="flex min-h-[320px] items-center justify-center rounded-xl border border-dashed border-[#404754] bg-[#10141a] text-sm text-[#95a2b6]">
              No sensor selected.
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function MetricTile({
  accent,
  helper,
  label,
  value,
}: {
  accent?: string;
  helper: string;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl border border-[#404754] bg-[#0b0f14] p-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
      <div className="font-tomorrow text-[10px] tracking-[0.2em] text-[#738194] uppercase">
        {label}
      </div>
      <div className="mt-1 font-mono text-2xl text-[#e3edf7] tabular-nums">
        {value}
      </div>
      <div className={`mt-1 text-xs text-[#95a2b6] ${accent ?? ""}`}>
        {helper}
      </div>
    </div>
  );
}

export function getSensorOverrideForPanel(
  override: SensorOverride | undefined,
) {
  return override ?? defaultSensorOverride();
}
