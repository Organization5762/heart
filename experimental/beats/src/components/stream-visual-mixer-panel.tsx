import { StreamCube } from "@/components/stream-cube";
import { Skeleton } from "@/components/ui/skeleton";

export type StreamVisualMixerPanelProps = {
  clockSeconds: number;
  imgURL: string | null;
  socketUrl: string;
  telemetrySensorLabel: string;
  telemetryTargetLabel: string;
  telemetryValue: number;
  useImageFallback: boolean;
  fps: number;
  sceneDistance: number;
  sceneGain: number;
  onContextError: () => void;
  sceneConfig: Parameters<typeof StreamCube>[0]["sceneConfig"];
};

const SIGNAL_BAR_COUNT = 16;

export function StreamVisualMixerPanel({
  clockSeconds,
  fps,
  imgURL,
  onContextError,
  sceneConfig,
  sceneDistance,
  sceneGain,
  socketUrl,
  telemetrySensorLabel,
  telemetryTargetLabel,
  telemetryValue,
  useImageFallback,
}: StreamVisualMixerPanelProps) {
  return (
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
            Tune the renderer, bind telemetry-reactive plugins, and rehearse
            sensor behavior against the live stream.
          </p>
        </div>
        <div className="grid gap-2 sm:grid-cols-3">
          <StatusChip label="Telemetry Sensor" value={telemetrySensorLabel} />
          <StatusChip
            label="Renderer"
            value={useImageFallback ? "Image fallback" : "Three.js"}
          />
          <StatusChip label="WebSocket" value={socketUrl} />
        </div>
      </div>

      <div className="mb-4 grid gap-3 lg:grid-cols-[1.2fr_0.8fr]">
        <TransportSignalCard
          clockSeconds={clockSeconds}
          telemetryValue={telemetryValue}
        />
        <ActiveModuleCard
          distance={sceneDistance}
          fps={fps}
          gain={sceneGain}
          telemetryTargetLabel={telemetryTargetLabel}
        />
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
            onContextError={onContextError}
            sceneConfig={sceneConfig}
            telemetryValue={telemetryValue}
          />
        )}
      </div>
    </div>
  );
}

export function StreamedImage({ imgURL }: { imgURL: string | null }) {
  if (!imgURL) {
    return <Skeleton className="size-full" />;
  }

  return <img src={imgURL} alt="stream" className="size-full object-contain" />;
}

function TransportSignalCard({
  clockSeconds,
  telemetryValue,
}: {
  clockSeconds: number;
  telemetryValue: number;
}) {
  return (
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
          {Array.from({ length: SIGNAL_BAR_COUNT }).map((_, index) => {
            const threshold = (index + 1) / SIGNAL_BAR_COUNT;
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
  );
}

function ActiveModuleCard({
  distance,
  fps,
  gain,
  telemetryTargetLabel,
}: {
  distance: number;
  fps: number;
  gain: number;
  telemetryTargetLabel: string;
}) {
  return (
    <div className="rounded-[1.2rem] border border-[#353c46] bg-[#0c1015] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
      <p className="font-tomorrow text-[10px] tracking-[0.24em] text-[#6f7d91] uppercase">
        Active Module
      </p>
      <p className="font-tomorrow mt-2 text-lg tracking-[0.12em] text-slate-100 uppercase">
        {telemetryTargetLabel} Reactor
      </p>
      <p className="mt-1 text-sm text-[#a4b0c2]">
        Gain {gain.toFixed(2)} | Camera {distance.toFixed(1)}u
      </p>
      <p className="mt-3 font-mono text-xs text-[#7f8ea3] uppercase">
        Render cadence {fps} FPS
      </p>
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
