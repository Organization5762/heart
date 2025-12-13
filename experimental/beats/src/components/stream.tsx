import { useStreamedImage } from "@/actions/ws/providers/ImageProvider";
import { useWS } from "@/actions/ws/websocket";
import { Antenna } from "lucide-react";
import { useState } from "react";

import { StreamCube } from "./stream-cube";
import { Separator } from "./ui/separator";
import { Skeleton } from "./ui/skeleton";

function getStatusClasses(streamIsActive: boolean) {
  return streamIsActive
    ? "text-green-500 status-green-blink"
    : "text-red-500 status-red-blink";
}

export function StreamStatus(
  {
    streamIsActive,
    ...divProps
  }: React.ComponentProps<"div"> & {
    streamIsActive: boolean;
  },
) {
  return (
    <div
      {...divProps}
      className="font-tomorrow text-muted-foreground flex items-center text-[0.7rem] uppercase justify-end"
    >
      <Antenna className={`h-[1rem] mr-1 ${getStatusClasses(streamIsActive)}`} />
      <span>{streamIsActive ? "Active" : "Not Active"}</span>
    </div>
  );
}

export function StreamedImage({ imgURL }: { imgURL: string | null }) {
  if (!imgURL) return <Skeleton className="size-full" />;

  return (
    <img
      src={imgURL}
      alt="stream"
      className="size-full object-contain"
    />
  );
}

export function Stream() {
  const ws = useWS();
  const { imgURL, isActive, fps } = useStreamedImage();
  const [useImageFallback, setUseImageFallback] = useState(false);

  return (
    <div className="flex h-full flex-col select-none">
      <div className="flex-1 w-full min-h-0">
        {useImageFallback ? (
          <StreamedImage imgURL={imgURL} />
        ) : (
          <StreamCube
            imgURL={imgURL}
            onContextError={() => setUseImageFallback(true)}
          />
        )}
      </div>

      <Separator className="my-4 flex-none" />

      {/* Footer */}
      <div className="flex-none mb-2 flex items-center justify-between gap-4 px-2">
        <span className="text-xs text-muted-foreground font-tomorrow uppercase">
          fps: <b>{isActive ? fps : 0}</b>
        </span>
        <div className="text-xs text-muted-foreground font-tomorrow">
          {ws?.socket?.url}
        </div>
        <StreamStatus streamIsActive={isActive} />
      </div>
    </div>
  );
}
