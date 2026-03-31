import {
  SensorLabPanel,
  getSensorOverrideForPanel,
} from "@/components/sensor-lab-panel";
import { useSensorSimulation } from "@/features/stream-console/use-sensor-simulation";

function uniquePeripheralCount(sensorIds: string[]) {
  return new Set(sensorIds).size;
}

export function PeripheralSensorDeck({
  preferredSensorKey,
}: {
  preferredSensorKey?: string;
}) {
  const {
    clockSeconds,
    overrides,
    resolvedSensors,
    selectedSensor,
    selectedSensorHistory,
    setSelectedSensorId,
    updateSensorOverride,
    resetSensorOverride,
    clearSelectedSensorHistory,
  } = useSensorSimulation(preferredSensorKey);

  return (
    <div id="sensor-deck" className="grid gap-6">
      <section className="rounded-[1.5rem] border border-[#2f353f] bg-[linear-gradient(180deg,_rgba(21,26,33,0.96),_rgba(11,14,19,0.99))] p-5 text-slate-100 shadow-[0_24px_60px_rgba(0,0,0,0.45)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <p className="font-tomorrow text-[11px] tracking-[0.24em] text-[#7f8ea3] uppercase">
              Sensor Console
            </p>
            <h2 className="font-tomorrow text-2xl tracking-[0.12em] uppercase">
              Live Sensor Deck
            </h2>
            <p className="max-w-3xl text-sm text-[#a4b0c2]">
              Inspect numeric channels discovered from connected peripherals,
              pick a live source, and rehearse override behavior without leaving
              the device catalog.
            </p>
          </div>
          <div className="rounded-[1rem] border border-[#39414c] bg-[#0b0f14] px-4 py-3 text-right shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
            <p className="font-tomorrow text-[10px] tracking-[0.22em] text-[#738194] uppercase">
              Clock
            </p>
            <p className="font-mono text-2xl text-[#e3edf7]">
              {clockSeconds.toFixed(1)}s
            </p>
          </div>
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-3">
          <SensorDeckMetric
            label="Channels"
            value={String(resolvedSensors.length)}
            helper="Numeric and boolean leaves available to the UI."
          />
          <SensorDeckMetric
            label="Peripherals"
            value={String(
              uniquePeripheralCount(
                resolvedSensors.map((sensor) => sensor.peripheralId),
              ),
            )}
            helper="Distinct devices contributing live sensor paths."
          />
          <SensorDeckMetric
            label="Selection"
            value={selectedSensor?.label ?? "Awaiting selection"}
            helper={selectedSensor?.path ?? "Choose a sensor from the rack."}
          />
        </div>
      </section>

      <SensorLabPanel
        clockSeconds={clockSeconds}
        onClearHistory={clearSelectedSensorHistory}
        onResetOverride={resetSensorOverride}
        onSelectSensor={setSelectedSensorId}
        onUpdateOverride={updateSensorOverride}
        override={getSensorOverrideForPanel(
          selectedSensor ? overrides[selectedSensor.id] : undefined,
        )}
        overrides={overrides}
        selectedSensor={selectedSensor}
        selectedSensorHistory={selectedSensorHistory}
        sensors={resolvedSensors}
      />
    </div>
  );
}

function SensorDeckMetric({
  helper,
  label,
  value,
}: {
  helper: string;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-[1rem] border border-[#39414c] bg-[#10141a] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
      <p className="font-tomorrow text-[10px] tracking-[0.22em] text-[#738194] uppercase">
        {label}
      </p>
      <p className="mt-2 truncate font-mono text-xl text-[#e3edf7]">{value}</p>
      <p className="mt-1 text-xs text-[#93a0b4]">{helper}</p>
    </div>
  );
}
