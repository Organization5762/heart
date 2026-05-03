import { Button } from "@/components/ui/button";
import { SensorCommandTerminal } from "@/components/sensor-command-terminal";
import { SensorHistoryChart } from "@/components/sensor-history-chart";
import { Input } from "@/components/ui/input";
import {
  defaultSensorOverride,
  formatSensorValue,
  type ResolvedSensorChannel,
  type SensorHistoryPoint,
  type SensorOverride,
} from "@/features/stream-console/sensor-simulation";
import { Activity, Gauge, ScanLine, SlidersHorizontal } from "lucide-react";
import { useState } from "react";

type SensorTreeNode = {
  id: string;
  label: string;
  path: string;
  children: SensorTreeNode[];
  sensor: ResolvedSensorChannel | null;
};

type SensorPeripheralGroup = {
  id: string;
  label: string;
  source: ResolvedSensorChannel["source"];
  sensors: ResolvedSensorChannel[];
  tree: SensorTreeNode[];
};

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
  const [sensorQuery, setSensorQuery] = useState("");
  const normalizedSensorQuery = sensorQuery.trim().toLowerCase();
  const visibleSensors =
    normalizedSensorQuery.length === 0
      ? sensors
      : sensors.filter((sensor) =>
          [
            sensor.label,
            sensor.id,
            sensor.path,
            sensor.source,
            sensor.peripheralId,
          ].some((field) =>
            field.toLowerCase().includes(normalizedSensorQuery),
          ),
        );
  const sensorGroups = buildSensorGroups(visibleSensors);

  return (
    <section className="beats-console-panel rounded-[1.5rem] p-4 md:p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="beats-console-kicker font-tomorrow text-[11px] tracking-[0.22em] uppercase">
            Sensor Rack
          </p>
          <h2 className="font-tomorrow text-lg tracking-[0.14em] text-slate-100 uppercase">
            External Control Console
          </h2>
          <p className="beats-console-copy max-w-2xl text-sm leading-6">
            Inspect live values, stream external overrides, and compare the
            resulting traces in one panel.
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
            <div className="mb-3">
              <Input
                type="search"
                value={sensorQuery}
                onChange={(event) => setSensorQuery(event.target.value)}
                placeholder="Search"
                aria-label="Search detected sensors"
                className="border-[#404754] bg-[#171c23] text-slate-100 placeholder:text-[#6f7d91]"
              />
            </div>
            <div className="space-y-2">
              {sensorGroups.length > 0 ? (
                sensorGroups.map((group) => (
                  <div
                    key={group.id}
                    className="rounded-xl border border-[#39414c] bg-[rgba(14,18,24,0.92)] p-3"
                  >
                    <div className="mb-3 flex items-start justify-between gap-3">
                      <div>
                        <p className="font-tomorrow text-[10px] tracking-[0.18em] text-[#7d8ba0] uppercase">
                          {group.source === "fake"
                            ? "Virtual Peripheral"
                            : "Live Peripheral"}
                        </p>
                        <h4 className="font-tomorrow text-sm tracking-[0.12em] text-slate-100 uppercase">
                          {group.label}
                        </h4>
                      </div>
                      <span className="font-tomorrow rounded-full border border-[#464e5b] px-2 py-0.5 text-[10px] tracking-[0.16em] text-[#96a3b7] uppercase">
                        {group.sensors.length} Channels
                      </span>
                    </div>
                    <div className="space-y-2">
                      {group.tree.map((node) => (
                        <SensorTreeBranch
                          key={node.id}
                          depth={0}
                          node={node}
                          onSelectSensor={onSelectSensor}
                          selectedSensorId={selectedSensor?.id ?? null}
                        />
                      ))}
                    </div>
                  </div>
                ))
              ) : (
                <div className="beats-console-empty rounded-xl border border-dashed border-[#404754] px-3 py-6 text-sm text-[#95a2b6]">
                  {normalizedSensorQuery.length > 0
                    ? `No sensors match "${sensorQuery.trim()}".`
                    : "Awaiting streamed sensors."}
                </div>
              )}
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
                      Release Control
                    </Button>
                  </div>
                </div>

                <div className="grid gap-3 md:grid-cols-3">
                  <MetricTile
                    label="Live"
                    value={formatSensorValue(selectedSensor.value, 2)}
                    helper={
                      selectedSensor.hasLiveValue
                        ? selectedSensor.displayValue
                        : "No live value until a generator takes control."
                    }
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
                    Control Source
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

function buildSensorGroups(
  sensors: ResolvedSensorChannel[],
): SensorPeripheralGroup[] {
  const groups = new Map<string, SensorPeripheralGroup>();

  sensors.forEach((sensor) => {
    const existing = groups.get(sensor.peripheralId);
    if (existing) {
      existing.sensors.push(sensor);
      return;
    }

    groups.set(sensor.peripheralId, {
      id: sensor.peripheralId,
      label: sensor.peripheralLabel,
      source: sensor.source,
      sensors: [sensor],
      tree: [],
    });
  });

  return Array.from(groups.values())
    .map((group) => ({
      ...group,
      tree: buildSensorTree(group.sensors),
    }))
    .sort((left, right) => left.label.localeCompare(right.label));
}

function buildSensorTree(sensors: ResolvedSensorChannel[]) {
  const root: SensorTreeNode[] = [];

  sensors.forEach((sensor) => {
    let branch = root;
    let accumulatedPath = "";

    sensor.pathSegments.forEach((segment, index) => {
      accumulatedPath = accumulatedPath
        ? `${accumulatedPath}.${segment}`
        : segment;
      let existing = branch.find((node) => node.path === accumulatedPath);

      if (!existing) {
        existing = {
          id: `${sensor.peripheralId}:${accumulatedPath}`,
          label: formatSensorSegment(segment),
          path: accumulatedPath,
          children: [],
          sensor: null,
        };
        branch.push(existing);
      }

      if (index === sensor.pathSegments.length - 1) {
        existing.sensor = sensor;
        return;
      }

      branch = existing.children;
    });
  });

  function sortTree(nodes: SensorTreeNode[]): SensorTreeNode[] {
    return nodes
      .map((node) => {
        return {
          ...node,
          children: sortTree(node.children),
        };
      })
      .sort((left, right) => left.label.localeCompare(right.label));
  }

  return sortTree(root);
}

function formatSensorSegment(segment: string) {
  return segment.replaceAll("_", " ");
}

function SensorTreeBranch({
  depth,
  node,
  onSelectSensor,
  selectedSensorId,
}: {
  depth: number;
  node: SensorTreeNode;
  onSelectSensor: (sensorId: string) => void;
  selectedSensorId: string | null;
}) {
  const sensor = node.sensor;

  if (sensor) {
    return (
      <button
        type="button"
        onClick={() => onSelectSensor(sensor.id)}
        className={`w-full rounded-xl border px-3 py-3 text-left transition duration-150 ${
          selectedSensorId === sensor.id
            ? "border-[#5b8cff] bg-[linear-gradient(180deg,_rgba(22,34,53,0.98),_rgba(15,23,37,0.98))] shadow-[inset_0_0_0_1px_rgba(91,140,255,0.2)]"
            : "border-[var(--beats-chip-border)] bg-[rgba(24,29,36,0.9)] hover:border-[#526074] hover:bg-[rgba(30,36,45,0.96)]"
        }`}
        style={{ marginLeft: `${depth * 0.8}rem` }}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-medium text-slate-100">
            {node.label}
          </span>
          <span className="font-tomorrow rounded-full border border-[#464e5b] px-2 py-0.5 text-[10px] tracking-[0.16em] text-[#96a3b7] uppercase">
            {sensor.source}
          </span>
        </div>
        <div className="mt-1 flex items-center justify-between gap-3 text-xs text-[#95a2b6]">
          <span className="truncate">{sensor.path}</span>
          <span>
            {sensor.hasLiveValue ? `Live ${sensor.displayValue}` : "Idle"}
          </span>
        </div>
        <div className="mt-2 flex items-center justify-between gap-3 text-xs text-[#95a2b6]">
          <span>Applied {formatSensorValue(sensor.effectiveValue, 2)}</span>
          <span className="font-mono text-[#c3cfdf]">{sensor.commandKey}</span>
        </div>
      </button>
    );
  }

  return (
    <div style={{ marginLeft: `${depth * 0.8}rem` }}>
      <div className="rounded-lg border border-dashed border-[#313842] bg-[#0f141a] px-3 py-2">
        <p className="font-tomorrow text-[11px] tracking-[0.18em] text-[#7d8ba0] uppercase">
          {node.label}
        </p>
      </div>
      <div className="mt-2 space-y-2">
        {node.children.map((child) => (
          <SensorTreeBranch
            key={child.id}
            depth={depth + 1}
            node={child}
            onSelectSensor={onSelectSensor}
            selectedSensorId={selectedSensorId}
          />
        ))}
      </div>
    </div>
  );
}
