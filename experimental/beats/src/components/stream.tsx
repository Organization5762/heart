import { useStreamedImage } from "@/actions/ws/providers/ImageProvider";
import { useWS } from "@/actions/ws/websocket";
import { DEFAULT_SCENE_CONFIGURATION } from "@/features/stream-console/scene-config";
import { useSensorSimulation } from "@/features/stream-console/use-sensor-simulation";
import { Antenna } from "lucide-react";
import { useCallback, useState } from "react";
import type { ComponentProps } from "react";

import { ScenePluginDock } from "./scene-plugin-dock";
import { SensorLabPanel, getSensorOverrideForPanel } from "./sensor-lab-panel";
import { StreamCube } from "./stream-cube";
import { Separator } from "./ui/separator";
import { Skeleton } from "./ui/skeleton";

function getStatusClasses(streamIsActive: boolean) {
  return streamIsActive
    ? "text-green-400 status-green-blink"
    : "text-rose-400 status-red-blink";
}

export function StreamStatus({
  streamIsActive,
  ...divProps
}: ComponentProps<"div"> & {
  streamIsActive: boolean;
}) {
  return (
    <div
      {...divProps}
      className="font-tomorrow flex items-center justify-end text-[0.7rem] tracking-[0.22em] text-[#94a3b8] uppercase"
    >
      <Antenna
        className={`mr-1 h-[1rem] ${getStatusClasses(streamIsActive)}`}
      />
      <span>{streamIsActive ? "Active" : "Offline"}</span>
    </div>
  );
}

export function StreamedImage({ imgURL }: { imgURL: string | null }) {
  if (!imgURL) {
    return <Skeleton className="size-full" />;
  }

  return <img src={imgURL} alt="stream" className="size-full object-contain" />;
}

export function Stream() {
  const ws = useWS();
  const { imgURL, isActive, fps } = useStreamedImage();
  const [useImageFallback, setUseImageFallback] = useState(false);
  const [sceneConfig, setSceneConfig] = useState(DEFAULT_SCENE_CONFIGURATION);
  const {
    clockSeconds,
    overrides,
    resolvedSensors,
    selectedSensor,
    selectedSensorHistory,
    selectedSensorId,
    setSelectedSensorId,
    updateSensorOverride,
    resetSensorOverride,
    clearSelectedSensorHistory,
  } = useSensorSimulation();

  const handleContextError = useCallback(() => {
    setUseImageFallback(true);
  }, []);

  const telemetrySensorId = sceneConfig.telemetry.sensorId ?? selectedSensorId;
  const telemetrySensor =
    resolvedSensors.find((sensor) => sensor.id === telemetrySensorId) ?? null;
  const telemetryValue = telemetrySensor?.effectiveValue ?? 0;

  return (
    <div className="flex h-full flex-col gap-4 rounded-[1.75rem] bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.08),_transparent_28%),linear-gradient(180deg,_#11151b,_#090b0f)] p-4 text-slate-100 shadow-[0_30px_80px_rgba(0,0,0,0.45)] select-none">
      <div className="rounded-[1.4rem] border border-[#2f353f] bg-[linear-gradient(180deg,_rgba(26,30,38,0.96),_rgba(14,17,23,0.98))] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="grid grid-cols-3 gap-1 rounded-[0.9rem] border border-[#3b434f] bg-[#0a0d12] p-2">
              {[
                isActive ? "#34d399" : "#29303a",
                telemetrySensor ? "#fbbf24" : "#29303a",
                useImageFallback ? "#fb7185" : "#38bdf8",
              ].map((color, index) => (
                <span
                  key={index}
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
            <div>
              <p className="font-tomorrow text-[11px] tracking-[0.26em] text-[#7f8ea3] uppercase">
                Beats Transport
              </p>
              <h1 className="font-tomorrow text-xl tracking-[0.14em] text-slate-100 uppercase">
                Scene Control Console
              </h1>
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            <TransportChip
              label="Clock"
              value={`${clockSeconds.toFixed(1)}s`}
            />
            <TransportChip label="FPS" value={String(isActive ? fps : 0)} />
            <TransportChip
              label="Sensor"
              value={telemetrySensor?.label ?? "Unassigned"}
            />
            <TransportChip
              label="Render"
              value={useImageFallback ? "Fallback" : "Realtime"}
            />
          </div>
        </div>
      </div>

      <div className="grid min-h-0 flex-1 gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(340px,420px)]">
        <section className="flex min-h-0 flex-col gap-4">
          <div className="rounded-[1.5rem] border border-[#2f353f] bg-[linear-gradient(180deg,_rgba(28,32,39,0.96),_rgba(13,16,21,0.98))] p-4 shadow-[0_24px_60px_rgba(0,0,0,0.45)]">
            <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="font-tomorrow text-[11px] tracking-[0.24em] text-[#7f8ea3] uppercase">
                  Stream Scene
                </p>
                <h2 className="font-tomorrow text-2xl tracking-[0.12em] text-slate-100 uppercase">
                  Visual Mixer
                </h2>
                <p className="mt-2 max-w-3xl text-sm text-[#a4b0c2]">
                  Tune the renderer, bind telemetry-reactive plugins, and
                  rehearse sensor behavior against the live stream.
                </p>
              </div>
              <div className="grid gap-2 sm:grid-cols-3">
                <StatusChip
                  label="Telemetry Sensor"
                  value={telemetrySensor?.label ?? "None"}
                />
                <StatusChip
                  label="Renderer"
                  value={useImageFallback ? "Image fallback" : "Three.js"}
                />
                <StatusChip
                  label="WebSocket"
                  value={ws?.socket?.url ?? "Disconnected"}
                />
              </div>
            </div>

            <div className="mb-4 grid gap-3 lg:grid-cols-[1.2fr_0.8fr]">
              <div className="rounded-[1.2rem] border border-[#353c46] bg-[#0c1015] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="font-tomorrow text-[10px] tracking-[0.24em] text-[#6f7d91] uppercase">
                      Transport
                    </p>
                    <p className="mt-1 font-mono text-2xl text-[#e3edf7]">
                      {clockSeconds.toFixed(1)}s
                    </p>
                  </div>
                  <div className="flex flex-1 items-end gap-1">
                    {Array.from({ length: 16 }).map((_, index) => {
                      const threshold = (index + 1) / 16;
                      const signal = Math.abs(Math.tanh(telemetryValue));
                      const active = signal >= threshold;
                      return (
                        <span
                          key={index}
                          className="flex-1 rounded-sm"
                          style={{
                            height: `${index > 11 ? 38 : index > 7 ? 30 : 22}px`,
                            backgroundColor: active
                              ? index > 12
                                ? "#fb7185"
                                : index > 8
                                  ? "#fbbf24"
                                  : "#34d399"
                              : "#1d242d",
                          }}
                        />
                      );
                    })}
                  </div>
                </div>
              </div>

              <div className="rounded-[1.2rem] border border-[#353c46] bg-[#0c1015] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
                <p className="font-tomorrow text-[10px] tracking-[0.24em] text-[#6f7d91] uppercase">
                  Active Module
                </p>
                <p className="font-tomorrow mt-2 text-lg tracking-[0.12em] text-slate-100 uppercase">
                  {sceneConfig.telemetry.target} Reactor
                </p>
                <p className="mt-1 text-sm text-[#a4b0c2]">
                  Gain {sceneConfig.telemetry.gain.toFixed(2)} | Camera{" "}
                  {sceneConfig.camera.distance.toFixed(1)}u
                </p>
              </div>
            </div>

            <div className="min-h-0">
              {useImageFallback ? (
                <div className="relative min-h-[420px] overflow-hidden rounded-[1.5rem] border border-[#343b45] bg-[#0a0d12]">
                  <StreamedImage imgURL={imgURL} />
                  <div className="font-tomorrow absolute top-4 left-4 rounded-full border border-[#3b434f] bg-[#11161d] px-3 py-1 text-[11px] tracking-[0.2em] text-[#9ba8ba] uppercase">
                    WebGL fallback active
                  </div>
                </div>
              ) : (
                <StreamCube
                  imgURL={imgURL}
                  onContextError={handleContextError}
                  sceneConfig={sceneConfig}
                  telemetryValue={telemetryValue}
                />
              )}
            </div>
          </div>

          <div className="xl:hidden">
            <ScenePluginDock
              sceneConfig={sceneConfig}
              sensorOptions={resolvedSensors.map((sensor) => ({
                id: sensor.id,
                label: sensor.label,
              }))}
              onChange={setSceneConfig}
              onReset={() => setSceneConfig(DEFAULT_SCENE_CONFIGURATION)}
            />
          </div>

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
        </section>

        <aside className="hidden min-h-0 xl:flex xl:flex-col xl:gap-4">
          <ScenePluginDock
            sceneConfig={sceneConfig}
            sensorOptions={resolvedSensors.map((sensor) => ({
              id: sensor.id,
              label: sensor.label,
            }))}
            onChange={setSceneConfig}
            onReset={() => setSceneConfig(DEFAULT_SCENE_CONFIGURATION)}
          />
        </aside>
      </div>

      <Separator className="flex-none bg-[#252b33]" />

      <div className="mb-2 flex flex-none flex-wrap items-center justify-between gap-4 rounded-[1.1rem] border border-[#2f353f] bg-[#10141a] px-3 py-2">
        <span className="font-tomorrow text-[11px] tracking-[0.22em] text-[#7f8ea3] uppercase">
          fps: <b className="text-slate-100">{isActive ? fps : 0}</b>
        </span>
        <div className="font-mono text-xs text-[#8d9bb0]">
          {ws?.socket?.url}
        </div>
        <StreamStatus streamIsActive={isActive} />
      </div>
    </div>
  );
}

function StatusChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[1rem] border border-[#343c46] bg-[#0c1015] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
      <div className="font-tomorrow text-[10px] tracking-[0.2em] text-[#6f7d91] uppercase">
        {label}
      </div>
      <div className="mt-1 max-w-[180px] truncate font-mono text-sm text-[#dce6f5]">
        {value}
      </div>
    </div>
  );
}

function TransportChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-[108px] rounded-[0.95rem] border border-[#3a414c] bg-[#0b0e13] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
      <div className="font-tomorrow text-[10px] tracking-[0.22em] text-[#738194] uppercase">
        {label}
      </div>
      <div className="mt-1 truncate font-mono text-sm text-[#e5edf8]">
        {value}
      </div>
    </div>
  );
}
