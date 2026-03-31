import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DEFAULT_SCENE_CONFIGURATION,
  type SceneConfiguration,
} from "@/features/stream-console/scene-config";
import { cn } from "@/utils/tailwind";
import { Aperture, Boxes, Orbit, Radar, Sparkles, Zap } from "lucide-react";
import type { ReactNode } from "react";

type SensorOption = {
  id: string;
  label: string;
};

export function ScenePluginDock({
  sceneConfig,
  sensorOptions,
  onChange,
  onReset,
}: {
  sceneConfig: SceneConfiguration;
  sensorOptions: SensorOption[];
  onChange: (next: SceneConfiguration) => void;
  onReset: () => void;
}) {
  function updateMotion(patch: Partial<SceneConfiguration["motion"]>) {
    onChange({
      ...sceneConfig,
      motion: {
        ...sceneConfig.motion,
        ...patch,
      },
    });
  }

  function updateCamera(patch: Partial<SceneConfiguration["camera"]>) {
    onChange({
      ...sceneConfig,
      camera: {
        ...sceneConfig.camera,
        ...patch,
      },
    });
  }

  function updateStage(patch: Partial<SceneConfiguration["stage"]>) {
    onChange({
      ...sceneConfig,
      stage: {
        ...sceneConfig.stage,
        ...patch,
      },
    });
  }

  function updateSurface(patch: Partial<SceneConfiguration["surface"]>) {
    onChange({
      ...sceneConfig,
      surface: {
        ...sceneConfig.surface,
        ...patch,
      },
    });
  }

  function updateTelemetry(patch: Partial<SceneConfiguration["telemetry"]>) {
    onChange({
      ...sceneConfig,
      telemetry: {
        ...sceneConfig.telemetry,
        ...patch,
      },
    });
  }

  return (
    <section className="rounded-[1.5rem] border border-[#2f353f] bg-[linear-gradient(180deg,_rgba(29,33,40,0.96),_rgba(15,18,24,0.98))] p-4 shadow-[0_24px_60px_rgba(0,0,0,0.45)]">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <p className="font-tomorrow text-[11px] tracking-[0.22em] text-[#7f8ea3] uppercase">
            Device Rack
          </p>
          <h2 className="font-tomorrow text-lg tracking-[0.14em] text-slate-100 uppercase">
            Configurable Plugins
          </h2>
          <p className="text-sm text-[#a4b0c2]">
            Tune the stream scene like a modular effects chain.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onReset}
          className="border-[#404754] bg-[#10141a] text-slate-200 hover:bg-[#171c23]"
        >
          Reset
        </Button>
      </div>

      <div className="flex gap-3 overflow-x-auto pb-1 xl:grid xl:grid-cols-1 xl:overflow-visible">
        <PluginCard
          icon={<Orbit className="h-4 w-4" />}
          title="Motion"
          description="Drive cube rotation and idle drift."
          stateLabel={sceneConfig.motion.autoRotate ? "Armed" : "Manual"}
          tone="emerald"
        >
          <BooleanField
            label="Auto Rotate"
            value={sceneConfig.motion.autoRotate}
            onToggle={(value) => updateMotion({ autoRotate: value })}
          />
          <RangeField
            label="Pitch Speed"
            value={sceneConfig.motion.rotationX}
            min={0}
            max={0.05}
            step={0.001}
            onChange={(value) => updateMotion({ rotationX: value })}
          />
          <RangeField
            label="Yaw Speed"
            value={sceneConfig.motion.rotationY}
            min={0}
            max={0.05}
            step={0.001}
            onChange={(value) => updateMotion({ rotationY: value })}
          />
          <RangeField
            label="Wobble"
            value={sceneConfig.motion.wobbleAmount}
            min={0}
            max={0.5}
            step={0.01}
            onChange={(value) => updateMotion({ wobbleAmount: value })}
          />
          <RangeField
            label="Hover"
            value={sceneConfig.motion.hoverAmount}
            min={0}
            max={0.5}
            step={0.01}
            onChange={(value) => updateMotion({ hoverAmount: value })}
          />
        </PluginCard>

        <PluginCard
          icon={<Aperture className="h-4 w-4" />}
          title="Camera"
          description="Move the viewer closer or widen the lens."
          stateLabel={`${sceneConfig.camera.distance.toFixed(1)}u`}
          tone="sky"
        >
          <RangeField
            label="Distance"
            value={sceneConfig.camera.distance}
            min={2.5}
            max={8}
            step={0.1}
            onChange={(value) => updateCamera({ distance: value })}
          />
          <RangeField
            label="Field of View"
            value={sceneConfig.camera.fov}
            min={28}
            max={75}
            step={1}
            onChange={(value) => updateCamera({ fov: value })}
          />
        </PluginCard>

        <PluginCard
          icon={<Boxes className="h-4 w-4" />}
          title="Stage"
          description="Control lighting, grid, and background energy."
          stateLabel={sceneConfig.stage.showGrid ? "Live Grid" : "Grid Hidden"}
          tone="amber"
        >
          <BooleanField
            label="Grid"
            value={sceneConfig.stage.showGrid}
            onToggle={(value) => updateStage({ showGrid: value })}
          />
          <RangeField
            label="Grid Opacity"
            value={sceneConfig.stage.gridOpacity}
            min={0}
            max={0.8}
            step={0.01}
            onChange={(value) => updateStage({ gridOpacity: value })}
          />
          <RangeField
            label="Ambient Light"
            value={sceneConfig.stage.ambientIntensity}
            min={0}
            max={1.6}
            step={0.05}
            onChange={(value) => updateStage({ ambientIntensity: value })}
          />
          <RangeField
            label="Key Light"
            value={sceneConfig.stage.keyIntensity}
            min={0}
            max={2}
            step={0.05}
            onChange={(value) => updateStage({ keyIntensity: value })}
          />
          <RangeField
            label="Backdrop"
            value={sceneConfig.stage.backgroundTint}
            min={0}
            max={1}
            step={0.01}
            onChange={(value) => updateStage({ backgroundTint: value })}
          />
        </PluginCard>

        <PluginCard
          icon={<Sparkles className="h-4 w-4" />}
          title="Surface"
          description="Adjust cube scale and material response."
          stateLabel={`${sceneConfig.surface.textureRepeat.toFixed(1)}x tile`}
          tone="violet"
        >
          <RangeField
            label="Scale"
            value={sceneConfig.surface.cubeScale}
            min={0.8}
            max={2}
            step={0.02}
            onChange={(value) => updateSurface({ cubeScale: value })}
          />
          <RangeField
            label="Texture Repeat"
            value={sceneConfig.surface.textureRepeat}
            min={1}
            max={4}
            step={0.1}
            onChange={(value) => updateSurface({ textureRepeat: value })}
          />
          <RangeField
            label="Metalness"
            value={sceneConfig.surface.metalness}
            min={0}
            max={1}
            step={0.01}
            onChange={(value) => updateSurface({ metalness: value })}
          />
          <RangeField
            label="Roughness"
            value={sceneConfig.surface.roughness}
            min={0}
            max={1}
            step={0.01}
            onChange={(value) => updateSurface({ roughness: value })}
          />
        </PluginCard>

        <PluginCard
          icon={<Radar className="h-4 w-4" />}
          title="Telemetry Reactor"
          description="Let a sensor push motion, hover, or scale in real time."
          stateLabel={sceneConfig.telemetry.enabled ? "Coupled" : "Bypassed"}
          tone="rose"
        >
          <BooleanField
            label="Sensor Driven"
            value={sceneConfig.telemetry.enabled}
            onToggle={(value) => updateTelemetry({ enabled: value })}
          />
          <LabeledField label="Sensor">
            <select
              className="h-9 w-full rounded-md border border-[#404754] bg-[#0c1015] px-3 text-sm text-[#e3edf7]"
              value={sceneConfig.telemetry.sensorId ?? ""}
              onChange={(event) =>
                updateTelemetry({
                  sensorId: event.target.value || null,
                })
              }
            >
              <option value="">Use selected sensor</option>
              {sensorOptions.map((sensor) => (
                <option key={sensor.id} value={sensor.id}>
                  {sensor.label}
                </option>
              ))}
            </select>
          </LabeledField>
          <LabeledField label="Target">
            <select
              className="h-9 w-full rounded-md border border-[#404754] bg-[#0c1015] px-3 text-sm text-[#e3edf7]"
              value={sceneConfig.telemetry.target}
              onChange={(event) =>
                updateTelemetry({
                  target: event.target
                    .value as SceneConfiguration["telemetry"]["target"],
                })
              }
            >
              <option value="hover">Hover</option>
              <option value="rotation">Rotation</option>
              <option value="scale">Scale</option>
            </select>
          </LabeledField>
          <RangeField
            label="Gain"
            value={sceneConfig.telemetry.gain}
            min={0}
            max={0.5}
            step={0.01}
            onChange={(value) => updateTelemetry({ gain: value })}
          />
        </PluginCard>
      </div>

      <div className="mt-4 rounded-xl border border-[#3a414c] bg-[#0c1015] px-3 py-2 text-xs text-[#95a2b6]">
        Reset returns the scene to the default dock profile from{" "}
        <span className="font-mono text-[#e3edf7]">
          {DEFAULT_SCENE_CONFIGURATION.motion.rotationY.toFixed(3)}
        </span>{" "}
        yaw speed, a visible grid, and telemetry-driven hover.
      </div>
    </section>
  );
}

function PluginCard({
  children,
  description,
  icon,
  stateLabel,
  title,
  tone,
}: {
  children: ReactNode;
  description: string;
  icon: ReactNode;
  stateLabel: string;
  title: string;
  tone: "amber" | "emerald" | "rose" | "sky" | "violet";
}) {
  return (
    <section className="relative min-w-[280px] flex-1 overflow-hidden rounded-[1.25rem] border border-[#3a414c] bg-[linear-gradient(180deg,_rgba(39,44,54,0.96),_rgba(20,23,30,0.98))] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)] xl:min-w-0">
      <div
        className={cn(
          "absolute inset-y-0 left-0 w-1.5",
          toneMeterClassNames[tone],
        )}
      />
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
            <span
              className={cn(
                "rounded-[0.9rem] border border-white/8 p-2",
                toneClassNames[tone],
              )}
            >
              {icon}
            </span>
            {title}
          </div>
          <p className="text-xs text-[#a4b0c2]">{description}</p>
        </div>
        <span className="font-tomorrow rounded-full border border-[#454d59] bg-[#0d1116] px-2 py-1 text-[10px] tracking-[0.2em] text-[#9ca9bb] uppercase">
          {stateLabel}
        </span>
      </div>
      <div className="space-y-3">{children}</div>
    </section>
  );
}

function LabeledField({
  children,
  label,
}: {
  children: ReactNode;
  label: string;
}) {
  return (
    <label className="block space-y-2">
      <span className="font-tomorrow text-[10px] tracking-[0.2em] text-[#7f8ea3] uppercase">
        {label}
      </span>
      {children}
    </label>
  );
}

function RangeField({
  label,
  max,
  min,
  onChange,
  step,
  value,
}: {
  label: string;
  max: number;
  min: number;
  onChange: (next: number) => void;
  step: number;
  value: number;
}) {
  return (
    <label className="block space-y-2">
      <div className="font-tomorrow flex items-center justify-between gap-2 text-[10px] tracking-[0.2em] text-[#7f8ea3] uppercase">
        <span>{label}</span>
        <span className="rounded-md bg-[#0d1116] px-2 py-1 font-mono text-[#dce6f5]">
          {value.toFixed(step >= 1 ? 0 : step >= 0.1 ? 1 : 2)}
        </span>
      </div>
      <Input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="h-2 cursor-ew-resize border-[#404754] bg-[#0b0f14] px-0 py-0"
      />
    </label>
  );
}

function BooleanField({
  label,
  onToggle,
  value,
}: {
  label: string;
  onToggle: (value: boolean) => void;
  value: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-[#404754] bg-[#10141a] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <div>
        <div className="text-sm font-medium text-slate-100">{label}</div>
        <div className="text-xs text-[#8d9bb0]">
          {value ? "Enabled" : "Disabled"}
        </div>
      </div>
      <Button
        type="button"
        variant={value ? "default" : "outline"}
        size="sm"
        onClick={() => onToggle(!value)}
        className={
          value
            ? "bg-[#3b82f6] text-white hover:bg-[#2563eb]"
            : "border-[#404754] bg-[#171c23] text-slate-200 hover:bg-[#1f252d]"
        }
      >
        <Zap className="h-4 w-4" />
        {value ? "On" : "Off"}
      </Button>
    </div>
  );
}

const toneClassNames = {
  amber: "bg-amber-500/12 text-amber-300",
  emerald: "bg-emerald-500/12 text-emerald-300",
  rose: "bg-rose-500/12 text-rose-300",
  sky: "bg-sky-500/12 text-sky-300",
  violet: "bg-violet-500/12 text-violet-300",
};

const toneMeterClassNames = {
  amber: "bg-gradient-to-b from-amber-300 via-amber-500 to-amber-700",
  emerald: "bg-gradient-to-b from-emerald-300 via-emerald-500 to-emerald-700",
  rose: "bg-gradient-to-b from-rose-300 via-rose-500 to-rose-700",
  sky: "bg-gradient-to-b from-sky-300 via-sky-500 to-sky-700",
  violet: "bg-gradient-to-b from-violet-300 via-violet-500 to-violet-700",
};
