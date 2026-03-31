import { cn } from "@/utils/tailwind";

type StreamConsoleHeaderProps = {
  clockSeconds: number;
  isActive: boolean;
  selectedSensorLabel: string;
  useImageFallback: boolean;
};

export function StreamConsoleHeader({
  clockSeconds,
  isActive,
  selectedSensorLabel,
  useImageFallback,
}: StreamConsoleHeaderProps) {
  return (
    <div className="rounded-[1.4rem] border border-[#2f353f] bg-[linear-gradient(180deg,_rgba(26,30,38,0.96),_rgba(14,17,23,0.98))] px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
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
            <p className="font-tomorrow text-[11px] tracking-[0.26em] text-[#7f8ea3] uppercase">
              Beats Transport
            </p>
            <h1 className="font-tomorrow text-xl tracking-[0.14em] text-slate-100 uppercase">
              Scene Control Console
            </h1>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <TransportChip label="Clock" value={`${clockSeconds.toFixed(1)}s`} />
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
    <div className="grid grid-cols-3 gap-1 rounded-[0.9rem] border border-[#3b434f] bg-[#0a0d12] p-2">
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
    <div className="min-w-[108px] rounded-[0.95rem] border border-[#3a414c] bg-[#0b0e13] px-3 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
      <div className="font-tomorrow text-[10px] tracking-[0.22em] text-[#738194] uppercase">
        {label}
      </div>
      <div
        className={cn(
          "mt-1 truncate font-mono text-sm",
          value === "Unassigned" ? "text-[#94a3b8]" : "text-[#e5edf8]",
        )}
      >
        {value}
      </div>
    </div>
  );
}
