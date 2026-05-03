import { StreamCube } from "@/components/stream-cube";
import { Skeleton } from "@/components/ui/skeleton";

export type StreamVisualMixerPanelProps = {
  clockSeconds: number;
  frameBlob: Blob | null;
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
  frameBlob,
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
    <div className="beats-console-panel rounded-[1.5rem] p-4 md:p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="beats-console-kicker font-tomorrow text-[10px] tracking-[0.2em] uppercase">
            Stream Scene
          </p>
          <h2 className="font-tomorrow text-[1.55rem] tracking-[0.09em] text-slate-100 uppercase md:text-[1.65rem]">
            Visual Mixer
          </h2>
          <p className="beats-console-copy mt-2 max-w-3xl text-sm leading-5.5">
            Tune the renderer, bind telemetry-reactive plugins, and rehearse
            sensor behavior against the live stream.
          </p>
        </div>
        <div className="grid w-full gap-2 sm:grid-cols-3 xl:w-auto">
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
          <div className="beats-console-card relative min-h-[420px] overflow-hidden rounded-[1.5rem]">
            <StreamedImage imgURL={imgURL} />
            <div className="beats-console-chip font-tomorrow absolute top-4 left-4 rounded-full px-3 py-1 text-[11px] tracking-[0.2em] text-[#9ba8ba] uppercase">
              WebGL fallback active
            </div>
          </div>
        ) : (
          <StreamCube
            frameBlob={frameBlob}
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
    <div className="beats-console-card rounded-[1.2rem] px-4 py-3">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="beats-console-kicker font-tomorrow text-[10px] tracking-[0.24em] uppercase">
            Transport
          </p>
          <p className="beats-console-strong mt-1 font-mono text-2xl">
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
    <div className="beats-console-card rounded-[1.2rem] px-4 py-3">
      <p className="beats-console-kicker font-tomorrow text-[10px] tracking-[0.24em] uppercase">
        Active Module
      </p>
      <p className="font-tomorrow mt-2 text-lg tracking-[0.12em] text-slate-100 uppercase">
        {telemetryTargetLabel} Reactor
      </p>
      <p className="beats-console-copy mt-1 text-sm">
        Gain {gain.toFixed(2)} | Camera {distance.toFixed(1)}u
      </p>
      <p className="beats-console-kicker mt-3 font-mono text-xs uppercase">
        Render cadence {fps} FPS
      </p>
    </div>
  );
}

function StatusChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="beats-console-chip rounded-[1rem] px-3 py-2">
      <div className="beats-console-kicker font-tomorrow text-[10px] tracking-[0.2em] uppercase">
        {label}
      </div>
      <div className="beats-console-strong mt-1 max-w-[180px] truncate font-mono text-sm">
        {value}
      </div>
    </div>
  );
}
