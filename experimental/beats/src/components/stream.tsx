import { useStreamedImage } from "@/actions/ws/providers/ImageProvider";
import { useConnectedPeripherals } from "@/actions/ws/providers/PeripheralProvider";
import { useWS } from "@/actions/ws/websocket";
import {
  DataRow,
  MeterBar,
  PageFrame,
  PaperCard,
  SectionHeader,
  SpecChip,
  TechnicalCard,
} from "@/components/usgc";
import { Antenna, ScanLine } from "lucide-react";
import { useCallback, useState } from "react";
import type { ComponentProps } from "react";

import { StreamCube } from "./stream-cube";
import { Skeleton } from "./ui/skeleton";

function getStatusClasses(streamIsActive: boolean) {
  return streamIsActive
    ? "text-green-500 status-green-blink"
    : "text-red-500 status-red-blink";
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
      className="text-muted-foreground font-tomorrow flex items-center justify-end text-[0.7rem] tracking-[0.18em] uppercase"
    >
      <Antenna
        className={`mr-1 h-[1rem] ${getStatusClasses(streamIsActive)}`}
      />
      <span>{streamIsActive ? "Active" : "Not Active"}</span>
    </div>
  );
}

export function StreamedImage({ imgURL }: { imgURL: string | null }) {
  if (!imgURL) {
    return <Skeleton className="size-full min-h-[260px] rounded-none" />;
  }

  return (
    <div className="relative h-full min-h-[260px] w-full overflow-hidden border border-white/20 bg-[radial-gradient(circle_at_top,rgba(43,103,255,0.14),transparent_34%),linear-gradient(180deg,rgba(7,7,7,0.94),rgba(2,6,23,0.98))]">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,transparent,rgba(14,165,233,0.06)_58%,rgba(2,6,23,0.72))]" />
      <img
        src={imgURL}
        alt="stream"
        className="relative size-full object-contain p-4"
      />
    </div>
  );
}

function getReadyStateLabel(readyState: number | undefined) {
  switch (readyState) {
    case WebSocket.CONNECTING:
      return "Dialing";
    case WebSocket.OPEN:
      return "Online";
    case WebSocket.CLOSING:
      return "Closing";
    default:
      return "Offline";
  }
}

export function Stream() {
  const ws = useWS();
  const { imgURL, isActive, fps } = useStreamedImage();
  const peripherals = useConnectedPeripherals();
  const [useImageFallback, setUseImageFallback] = useState(false);
  const handleContextError = useCallback(() => {
    setUseImageFallback(true);
  }, []);
  const readyStateLabel = getReadyStateLabel(ws.readyState);
  const peripheralCount = Object.keys(peripherals).length;

  return (
    <PageFrame className="select-none">
      <PaperCard>
        <SectionHeader
          eyebrow="Current Stream / Imaging Chamber"
          title="Live Transmission Sheet"
          description="A specimen-grade viewport for the current feed, framed with cadence, socket, and device state."
          aside={
            <div className="flex flex-wrap gap-2">
              <SpecChip>{readyStateLabel}</SpecChip>
              <SpecChip tone="muted">
                {useImageFallback ? "Image Fallback" : "3D Viewport"}
              </SpecChip>
            </div>
          }
        />
      </PaperCard>

      <section className="grid min-h-0 flex-1 gap-6 xl:grid-cols-[0.82fr_1.18fr]">
        <PaperCard className="flex flex-col gap-6">
          <div className="space-y-3">
            <p className="usgc-kicker">Department Copy</p>
            <h2 className="font-tomorrow text-2xl tracking-[0.1em]">
              Houston Mono Signal Desk
            </h2>
            <p className="usgc-copy">
              The live stream surface treats each frame as a published artifact:
              signal quality, transport state, and render mode are exposed like
              a machine report rather than hidden in utility chrome.
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="border-border bg-background/75 border p-4">
              <p className="usgc-kicker">Frame Cadence</p>
              <p className="font-tomorrow mt-3 text-3xl tracking-[0.12em]">
                {isActive ? fps : 0}
              </p>
              <p className="text-muted-foreground mt-2 font-mono text-[0.68rem] tracking-[0.18em] uppercase">
                Frames per second
              </p>
            </div>
            <div className="border-border bg-background/75 border p-4">
              <p className="usgc-kicker">Input Surface</p>
              <p className="font-tomorrow mt-3 text-3xl tracking-[0.12em]">
                {peripheralCount}
              </p>
              <p className="text-muted-foreground mt-2 font-mono text-[0.68rem] tracking-[0.18em] uppercase">
                Registered peripherals
              </p>
            </div>
          </div>

          <div className="grid gap-4">
            <MeterBar
              label="Cadence Confidence"
              value={Math.min(isActive ? fps : 0, 60)}
              max={60}
              valueLabel={`${isActive ? fps : 0} FPS`}
            />
            <MeterBar
              label="Socket Readiness"
              value={ws.readyState === WebSocket.OPEN ? 100 : 25}
              valueLabel={readyStateLabel}
            />
          </div>

          <div className="space-y-1 font-mono text-sm">
            <DataRow
              label="Transport"
              value={ws?.socket?.url ?? "ws://localhost:8765"}
            />
            <DataRow
              label="Renderer"
              value={useImageFallback ? "2D PNG" : "WebGL Display"}
            />
            <DataRow
              label="Signal"
              value={isActive ? "Frames observed" : "Awaiting frames"}
            />
          </div>
        </PaperCard>

        <TechnicalCard className="flex min-h-[560px] flex-col gap-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="space-y-2">
              <p className="usgc-kicker text-[#bdb3a6]">TR-100 Live Viewport</p>
              <h2 className="font-tomorrow text-2xl tracking-[0.12em] text-[#f6efe6]">
                Transmission Chamber
              </h2>
            </div>
            <StreamStatus streamIsActive={isActive} />
          </div>

          <div className="usgc-terminal-grid flex-1 border border-white/20 p-3">
            <div className="flex h-full min-h-[360px] flex-col border border-white/15 bg-black/35 p-3">
              <div className="mb-3 flex items-center justify-between font-mono text-[0.68rem] tracking-[0.18em] text-[#cfc6bb] uppercase">
                <span className="flex items-center gap-2">
                  <ScanLine className="size-3.5" />
                  Surface Feed
                </span>
                <span>
                  {useImageFallback ? "Fallback Raster" : "Realtime WebGL"}
                </span>
              </div>
              <div className="flex-1">
                {useImageFallback ? (
                  <StreamedImage imgURL={imgURL} />
                ) : (
                  <StreamCube
                    imgURL={imgURL}
                    onContextError={handleContextError}
                  />
                )}
              </div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <p className="usgc-kicker text-[#bdb3a6]">Socket</p>
              <p className="mt-2 font-mono text-sm">{readyStateLabel}</p>
            </div>
            <div>
              <p className="usgc-kicker text-[#bdb3a6]">Stream URL</p>
              <p className="mt-2 font-mono text-sm">
                {ws?.socket?.url ?? "Unavailable"}
              </p>
            </div>
            <div>
              <p className="usgc-kicker text-[#bdb3a6]">Mode</p>
              <p className="mt-2 font-mono text-sm">
                {useImageFallback ? "PNG" : "Three.js"}
              </p>
            </div>
          </div>
        </TechnicalCard>
      </section>

      <div className="border-border flex flex-none items-center justify-between gap-4 border-t px-1 pt-2">
        <span className="text-muted-foreground font-tomorrow text-xs uppercase">
          fps: <b>{isActive ? fps : 0}</b>
        </span>
        <div className="text-muted-foreground font-tomorrow text-xs">
          {ws?.socket?.url}
        </div>
        <StreamStatus streamIsActive={isActive} />
      </div>
    </PageFrame>
  );
}
