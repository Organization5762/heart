import { Antenna } from "lucide-react";
import type { ComponentProps } from "react";

import { Separator } from "./ui/separator";

function getStatusClasses(streamIsActive: boolean) {
  return streamIsActive
    ? "text-green-400 status-green-blink"
    : "text-rose-400 status-red-blink";
}

export function StreamFooterBar({
  fps,
  socketUrl,
  streamIsActive,
}: {
  fps: number;
  socketUrl: string;
  streamIsActive: boolean;
}) {
  return (
    <>
      <Separator className="flex-none bg-[#252b33]" />

      <div className="mb-2 flex flex-none flex-wrap items-center justify-between gap-4 rounded-[1.1rem] border border-[#2f353f] bg-[#10141a] px-3 py-2">
        <span className="font-tomorrow text-[11px] tracking-[0.22em] text-[#7f8ea3] uppercase">
          fps: <b className="text-slate-100">{fps}</b>
        </span>
        <div className="font-mono text-xs text-[#8d9bb0]">{socketUrl}</div>
        <StreamStatus streamIsActive={streamIsActive} />
      </div>
    </>
  );
}

function StreamStatus({
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
