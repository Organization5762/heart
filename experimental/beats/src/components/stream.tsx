import { Antenna } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Separator } from "./ui/separator";
import { Skeleton } from "./ui/skeleton";
import { useWS } from "./websocket";

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
  }
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



export function useStreamedImage(
  ws: WebSocket | null,
  {
    recentThreshold = 1500,
    fpsWindow = 5000,
    eventType = "frame",
  } = {}
) {
  const [imgURL, setImgURL] = useState<string | null>(null);
  const [isActive, setIsActive] = useState(false);
  const [fps, setFps] = useState(0);

  const lastFrameRef = useRef<number>(0);
  const frameTimesRef = useRef<number[]>([]);

  useEffect(() => {
    if (!ws) return;

    const onMessage = async (event: MessageEvent) => {
      const text = await event.data.text();
      const msg = JSON.parse(text);
      if (msg.type !== eventType) return;

      const now = performance.now();
      lastFrameRef.current = now;

      // --- FPS smoothing ---
      frameTimesRef.current.push(now);

      // Remove old frames
      const cutoff = now - fpsWindow;
      while (frameTimesRef.current.length && frameTimesRef.current[0] < cutoff) {
        frameTimesRef.current.shift();
      }
      
      const frames = frameTimesRef.current.length;
      const windowStart = frameTimesRef.current[0] ?? now;
      const actualWindowMs = now - windowStart;
      const actualWindowSec = actualWindowMs / 1000;
      const fullWindowSec = fpsWindow / 1000;
      
      let computedFPS;
      
      // If the window isn't full yet (< 5 seconds of history)
      // → interpolate upwards (instantaneous rate)
      if (actualWindowSec < fullWindowSec) {
        computedFPS = frames / actualWindowSec;
      } else {
        // Full smoothing window → stable FPS
        computedFPS = frames / fullWindowSec;
      }
      
      setFps(Number(computedFPS.toFixed(0)));

      // --- Decode base64 PNG data ---
      const b64 = msg.payload;
      const blob = base64ToBlob(b64);
      const newURL = URL.createObjectURL(blob);

      setImgURL((old) => {
        if (old) URL.revokeObjectURL(old);
        return newURL;
      });

      setIsActive(true);
    };

    ws.addEventListener("message", onMessage);

    // Active/inactive updater
    const interval = setInterval(() => {
      const now = performance.now();
      setIsActive(now - lastFrameRef.current < recentThreshold);
    }, 200);

    return () => {
      ws.removeEventListener("message", onMessage);
      clearInterval(interval);

      setImgURL((old) => {
        if (old) URL.revokeObjectURL(old);
        return null;
      });

      setIsActive(false);
      setFps(0);
      frameTimesRef.current = [];
    };
  }, [ws, eventType, recentThreshold, fpsWindow]);

  return [imgURL, isActive, fps] as const;
}

// --- Helpers ---
function base64ToBlob(b64: string) {
  const byteChars = atob(b64);
  const arr = new Uint8Array(byteChars.length);
  for (let i = 0; i < byteChars.length; i++) arr[i] = byteChars.charCodeAt(i);
  return new Blob([arr], { type: "image/png" });
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
  const [imgURL, isActive, fps] = useStreamedImage(ws, { eventType: "frame" });

  return (
    <div className="flex h-full flex-col select-none">
      <div className="flex-1 w-full" />

      {/* Display the streamed image */}
      <StreamedImage imgURL={imgURL} />

      <Separator className="my-4 flex-none" />

      {/* Footer */}
      <div className="flex-none mb-2 flex items-center justify-between gap-4 px-2">
        <span className="text-xs text-muted-foreground font-tomorrow uppercase">
        fps: <b>{isActive ? fps : 0}</b>
        </span>
        <div className="text-xs text-muted-foreground font-tomorrow" >
          {ws?.url}
        </div>
        <StreamStatus streamIsActive={isActive} />
      </div>
    </div>
  );
}