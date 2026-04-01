import { createContext, useContext, useEffect, useState } from "react";

import { useRef } from "react";
import { frameStream } from "../streams";

const ACTIVE_STATUS_POLL_INTERVAL_MS = 200;
const STALE_URL_REVOKE_DELAY_MS = 1000;

type ImageState = {
  imgURL: string | null;
  frameBlob: Blob | null;
  isActive: boolean;
  fps: number;
};

type ImageProviderProps = {
  recentThreshold?: number;
  fpsWindow?: number;
  children: React.ReactNode;
};

const ImageContext = createContext<ImageState>({
  imgURL: null,
  frameBlob: null,
  isActive: false,
  fps: 0,
});

export function ImageProvider({
  recentThreshold = 1500,
  fpsWindow = 5000,
  children,
}: ImageProviderProps) {
  const [imgURL, setImgURL] = useState<string | null>(null);
  const [frameBlob, setFrameBlob] = useState<Blob | null>(null);
  const [isActive, setIsActive] = useState(false);
  const [fps, setFps] = useState(0);

  const lastFrameRef = useRef<number>(0);
  const frameTimesRef = useRef<number[]>([]);
  const revokeTimeoutsRef = useRef<number[]>([]);

  const clearPendingRevocations = () => {
    revokeTimeoutsRef.current.forEach((timeoutId) => {
      window.clearTimeout(timeoutId);
    });
    revokeTimeoutsRef.current = [];
  };

  const scheduleUrlRevocation = (url: string) => {
    const timeoutId = window.setTimeout(() => {
      URL.revokeObjectURL(url);
      revokeTimeoutsRef.current = revokeTimeoutsRef.current.filter(
        (pendingId) => pendingId !== timeoutId,
      );
    }, STALE_URL_REVOKE_DELAY_MS);
    revokeTimeoutsRef.current.push(timeoutId);
  };

  useEffect(() => {
    const sub = frameStream.subscribe((msg) => {
      const now = performance.now();
      lastFrameRef.current = now;

      // --- FPS smoothing ---
      frameTimesRef.current.push(now);

      // Remove old frames
      const cutoff = now - fpsWindow;
      while (
        frameTimesRef.current.length &&
        frameTimesRef.current[0] < cutoff
      ) {
        frameTimesRef.current.shift();
      }

      const frames = frameTimesRef.current.length;
      const windowStart = frameTimesRef.current[0] ?? now;
      const actualWindowMs = now - windowStart;
      const actualWindowSec = actualWindowMs / 1000;
      const fullWindowSec = fpsWindow / 1000;

      let computedFPS;
      if (actualWindowSec < fullWindowSec) {
        computedFPS = frames / actualWindowSec;
      } else {
        computedFPS = frames / fullWindowSec;
      }

      setFps(Number(computedFPS.toFixed(0)));

      const blob = bytesToBlob(msg.payload.pngData);
      const newURL = URL.createObjectURL(blob);
      setFrameBlob(blob);

      setImgURL((old) => {
        if (old) {
          scheduleUrlRevocation(old);
        }
        return newURL;
      });

      setIsActive(true);
    });

    // Active/inactive updater
    const interval = setInterval(() => {
      const now = performance.now();
      setIsActive(now - lastFrameRef.current < recentThreshold);
    }, ACTIVE_STATUS_POLL_INTERVAL_MS);

    return () => {
      sub.unsubscribe();
      clearInterval(interval);
      clearPendingRevocations();

      setImgURL((old) => {
        if (old) {
          URL.revokeObjectURL(old);
        }
        return null;
      });

      setFrameBlob(null);
      setIsActive(false);
      setFps(0);
      frameTimesRef.current = [];
    };
  }, [recentThreshold, fpsWindow]);

  return (
    <ImageContext.Provider
      value={{
        imgURL,
        frameBlob,
        isActive,
        fps,
      }}
    >
      {children}
    </ImageContext.Provider>
  );
}

export function useStreamedImage() {
  return useContext(ImageContext);
}

// --- Helpers ---
function bytesToBlob(data: Uint8Array) {
  const copy = new Uint8Array(data.byteLength);
  copy.set(data);
  return new Blob([copy], { type: "image/png" });
}
