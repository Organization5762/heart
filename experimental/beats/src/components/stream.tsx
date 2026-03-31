import { useStreamedImage } from "@/actions/ws/providers/ImageProvider";
import { useWS } from "@/actions/ws/websocket";
import { DEFAULT_SCENE_CONFIGURATION } from "@/features/stream-console/scene-config";
import { useSensorSimulation } from "@/features/stream-console/use-sensor-simulation";
import { useCallback, useState } from "react";

import { ScenePluginDock } from "./scene-plugin-dock";
import { SensorLabPanel, getSensorOverrideForPanel } from "./sensor-lab-panel";
import { StreamConsoleHeader } from "./stream-console-header";
import { StreamFooterBar } from "./stream-footer-bar";
import { StreamVisualMixerPanel } from "./stream-visual-mixer-panel";

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
  const socketUrl = ws?.socket?.url ?? "Disconnected";
  const telemetrySensorLabel = telemetrySensor?.label ?? "Unassigned";
  const activeFps = isActive ? fps : 0;

  return (
    <div className="beats-console-shell flex min-h-full flex-col gap-4 rounded-[1.75rem] p-4 text-slate-100 select-none md:p-5">
      <StreamConsoleHeader
        clockSeconds={clockSeconds}
        fps={activeFps}
        isActive={isActive}
        selectedSensorLabel={telemetrySensorLabel}
        useImageFallback={useImageFallback}
      />

      <div className="grid min-h-0 flex-1 gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(340px,420px)]">
        <section className="flex min-h-0 min-w-0 flex-col gap-4">
          <StreamVisualMixerPanel
            clockSeconds={clockSeconds}
            fps={activeFps}
            imgURL={imgURL}
            onContextError={handleContextError}
            sceneConfig={sceneConfig}
            sceneDistance={sceneConfig.camera.distance}
            sceneGain={sceneConfig.telemetry.gain}
            socketUrl={socketUrl}
            telemetrySensorLabel={telemetrySensorLabel}
            telemetryTargetLabel={sceneConfig.telemetry.target}
            telemetryValue={telemetryValue}
            useImageFallback={useImageFallback}
          />

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
            selectedSensor={selectedSensor}
            selectedSensorHistory={selectedSensorHistory}
            sensors={resolvedSensors}
          />
        </section>

        <aside className="hidden min-h-0 min-w-0 xl:flex xl:flex-col xl:gap-4">
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

      <StreamFooterBar
        fps={activeFps}
        socketUrl={socketUrl}
        streamIsActive={isActive}
      />
    </div>
  );
}
