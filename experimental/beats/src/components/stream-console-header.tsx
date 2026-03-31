import { cn } from "@/utils/tailwind";

type StreamConsoleHeaderProps = {
  clockSeconds: number;
  fps: number;
  isActive: boolean;
  selectedSensorLabel: string;
  useImageFallback: boolean;
};

export function StreamConsoleHeader({
  clockSeconds,
  fps,
  isActive,
  selectedSensorLabel,
  useImageFallback,
}: StreamConsoleHeaderProps) {
  return (
    <div className="beats-console-panel rounded-[1.4rem] px-4 py-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <SignalStack
            lights={[
              isActive ? "#34d399" : "#29303a",
              selectedSensorLabel !== "Unassigned" ? "#fbbf24" : "#29303a",
              useImageFallback ? "#fb7185" : "#38bdf8",
            ]}
          />
          <div>
            <p className="beats-console-kicker font-tomorrow text-[11px] tracking-[0.26em] uppercase">
              Beats Transport
            </p>
            <h1 className="font-tomorrow text-xl tracking-[0.14em] text-slate-100 uppercase md:text-[1.65rem]">
              Scene Control Console
            </h1>
          </div>
        </div>

        <div className="grid flex-1 gap-2 sm:grid-cols-2 xl:max-w-[540px] xl:grid-cols-4">
          <TransportChip label="Clock" value={`${clockSeconds.toFixed(1)}s`} />
          <TransportChip label="FPS" value={String(fps)} />
          <TransportChip label="Sensor" value={selectedSensorLabel} />
          <TransportChip
            label="Render"
            value={useImageFallback ? "Fallback" : "Realtime"}
          />
          <TransportChip label="Signal" value={isActive ? "Online" : "Idle"} />
        </div>
      </div>
    </div>
  );
}

function SignalStack({ lights }: { lights: string[] }) {
  return (
    <div className="beats-console-card grid grid-cols-3 gap-1 rounded-[0.9rem] p-2">
      {lights.map((color, index) => (
        <span
          key={index}
          className="h-2.5 w-2.5 rounded-full"
          style={{ backgroundColor: color }}
        />
      ))}
    </div>
  );
}

function TransportChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="beats-console-chip min-w-[108px] rounded-[0.95rem] px-3 py-2">
      <div className="beats-console-kicker font-tomorrow text-[10px] tracking-[0.22em] uppercase">
        {label}
      </div>
      <div
        className={cn(
          "mt-1 truncate font-mono text-sm",
          value === "Unassigned" ? "text-[#94a3b8]" : "beats-console-strong",
        )}
      >
        {value}
      </div>
    </div>
  );
}
