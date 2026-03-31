import { useStreamedImage } from "@/actions/ws/providers/ImageProvider";
import { useWS } from "@/actions/ws/websocket";
import { Antenna } from "lucide-react";
import { useCallback, useState } from "react";
import type { ComponentProps } from "react";

import { StreamCube } from "./stream-cube";
import { Separator } from "./ui/separator";
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
      className="font-tomorrow text-muted-foreground flex items-center justify-end text-[0.7rem] uppercase"
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
    return <Skeleton className="size-full min-h-[260px] rounded-xl" />;
  }

  return (
    <div className="border-border/60 relative h-full min-h-[260px] w-full overflow-hidden rounded-xl border bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.12),transparent_34%),linear-gradient(180deg,rgba(15,23,42,0.92),rgba(2,6,23,0.98))] shadow-[0_24px_80px_rgba(2,6,23,0.45)]">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,transparent,rgba(14,165,233,0.06)_58%,rgba(2,6,23,0.72))]" />
      <img
        src={imgURL}
        alt="stream"
        className="relative size-full object-contain p-4"
      />
    </div>
  );
}

export function Stream() {
  const ws = useWS();
  const { imgURL, isActive, fps } = useStreamedImage();
  const [useImageFallback, setUseImageFallback] = useState(false);
  const handleContextError = useCallback(() => {
    setUseImageFallback(true);
  }, []);

  return (
    <div className="flex h-full flex-col select-none">
      <div className="min-h-0 w-full flex-1">
        {useImageFallback ? (
          <StreamedImage imgURL={imgURL} />
        ) : (
          <StreamCube imgURL={imgURL} onContextError={handleContextError} />
        )}
      </div>

      <Separator className="my-4 flex-none" />

      {/* Footer */}
      <div className="mb-2 flex flex-none items-center justify-between gap-4 px-2">
        <span className="text-muted-foreground font-tomorrow text-xs uppercase">
          fps: <b>{isActive ? fps : 0}</b>
        </span>
        <div className="text-muted-foreground font-tomorrow text-xs">
          {ws?.socket?.url}
        </div>
        <StreamStatus streamIsActive={isActive} />
      </div>
    </div>
  );
}
