import { createContext, useContext, useEffect, useState } from "react";

import { useRef } from "react";
import { frameStream } from "../streams";

type ImageState = {
  imgURL: string | null;
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
  isActive: false,
  fps: 0,
});

export function ImageProvider({
  recentThreshold = 1500,
  fpsWindow = 5000,
  children,
}: ImageProviderProps) {
  const [imgURL, setImgURL] = useState<string | null>(null);
  const [isActive, setIsActive] = useState(false);
  const [fps, setFps] = useState(0);

  const lastFrameRef = useRef<number>(0);
  const frameTimesRef = useRef<number[]>([]);

  useEffect(() => {
    const sub = frameStream.subscribe((msg) => {
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
      if (actualWindowSec < fullWindowSec) {
        computedFPS = frames / actualWindowSec;
      } else {
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
    });

    // Active/inactive updater
    const interval = setInterval(() => {
      const now = performance.now();
      setIsActive(now - lastFrameRef.current < recentThreshold);
    }, 200);

    return () => {
      sub.unsubscribe();
      clearInterval(interval);

      setImgURL((old) => {
        if (old) URL.revokeObjectURL(old);
        return null;
      });

      setIsActive(false);
      setFps(0);
      frameTimesRef.current = [];
    };
  }, [recentThreshold, fpsWindow]);

  return (
    <ImageContext.Provider
      value={{
        imgURL,
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
function base64ToBlob(b64: string) {
  const byteChars = atob(b64);
  const arr = new Uint8Array(byteChars.length);
  for (let i = 0; i < byteChars.length; i++) arr[i] = byteChars.charCodeAt(i);
  return new Blob([arr], { type: "image/png" });
}