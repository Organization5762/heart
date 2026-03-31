import { Button } from "@/components/ui/button";
import { SensorCommandTerminal } from "@/components/sensor-command-terminal";
import { SensorHistoryChart } from "@/components/sensor-history-chart";
import {
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
  overrides,
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
  overrides: Record<string, SensorOverride>;
  selectedSensor: ResolvedSensorChannel | null;
  selectedSensorHistory: SensorHistoryPoint[];
  sensors: ResolvedSensorChannel[];
}) {
  return (
    <section className="beats-console-panel rounded-[1.5rem] p-4 md:p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="beats-console-kicker font-tomorrow text-[11px] tracking-[0.22em] uppercase">
            Sensor Rack
          </p>
          <h2 className="font-tomorrow text-lg tracking-[0.14em] text-slate-100 uppercase">
            Mocking and Trace Console
          </h2>
          <p className="beats-console-copy max-w-2xl text-sm leading-6">
            Compare live values, applied overrides, and time-driven functions in
            one panel.
          </p>
        </div>
        <div className="beats-console-card rounded-xl px-3 py-2 text-right">
          <div className="beats-console-kicker font-tomorrow text-[10px] tracking-[0.2em] uppercase">
            Simulation Clock
          </div>
          <div className="beats-console-strong font-mono text-xl">
            {clockSeconds.toFixed(1)}s
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(250px,280px)_minmax(0,1fr)]">
        <div className="space-y-3">
          <div className="beats-console-card rounded-xl p-3">
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
                  className={`w-full rounded-xl border px-3 py-3 text-left transition duration-150 ${
                    selectedSensor?.id === sensor.id
                      ? "border-[#5b8cff] bg-[linear-gradient(180deg,_rgba(22,34,53,0.98),_rgba(15,23,37,0.98))] shadow-[inset_0_0_0_1px_rgba(91,140,255,0.2)]"
                      : "border-[var(--beats-chip-border)] bg-[rgba(24,29,36,0.9)] hover:border-[#526074] hover:bg-[rgba(30,36,45,0.96)]"
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
              <div className="beats-console-card rounded-xl p-4">
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

              <div className="beats-console-card rounded-xl p-4">
                <div className="mb-4 flex items-center gap-2">
                  <SlidersHorizontal className="h-4 w-4 text-violet-500" />
                  <h3 className="font-tomorrow text-sm tracking-[0.12em] text-slate-100 uppercase">
                    Mock Source
                  </h3>
                </div>
                <SensorCommandTerminal
                  onClearHistory={onClearHistory}
                  onResetOverride={onResetOverride}
                  onSelectSensor={onSelectSensor}
                  onUpdateOverride={onUpdateOverride}
                  overrides={overrides}
                  selectedSensor={selectedSensor}
                  sensors={sensors}
                />
              </div>

              <div className="beats-console-card rounded-xl p-4">
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
            <div className="beats-console-empty flex min-h-[320px] items-center justify-center rounded-xl text-sm text-[#95a2b6]">
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
    <div className="beats-console-card rounded-xl p-3">
      <div className="beats-console-kicker font-tomorrow text-[10px] tracking-[0.2em] uppercase">
        {label}
      </div>
      <div className="beats-console-strong mt-1 font-mono text-2xl tabular-nums">
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
