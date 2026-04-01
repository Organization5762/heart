import { useEffect, useRef, useState } from "react";
import { type SceneConfiguration } from "@/features/stream-console/scene-config";
import {
  AmbientLight,
  BoxGeometry,
  CanvasTexture,
  DirectionalLight,
  GridHelper,
  Mesh,
  MeshStandardMaterial,
  PerspectiveCamera,
  RepeatWrapping,
  Scene,
  SRGBColorSpace,
  Texture,
  WebGLRenderer,
} from "three";

import { Skeleton } from "./ui/skeleton";

const GRID_SIZE = 6;
const GRID_DIVISIONS = 10;
const GRID_COLOR = 0xffffff;
const GRID_BASELINE_Y = -1.2;
const MAX_TELEMETRY_SIGNAL = 1;
const STREAM_TEXTURE_SIZE = 256;
const STREAM_TEXTURE_BACKGROUND = "#020617";
type DecodedStreamFrame = HTMLImageElement | ImageBitmap;
type FaceViewport = {
  left: number;
  top: number;
  width: number;
  height: number;
  usesStreamFrame: boolean;
};
type FaceTextureRuntime = {
  canvas: HTMLCanvasElement;
  context: CanvasRenderingContext2D;
  texture: CanvasTexture;
  viewport: FaceViewport;
};
type NormalizedStripRect = {
  left: number;
  top: number;
  size: number;
};

const CUBE_FACE_VIEWPORTS: FaceViewport[] = [
  { left: 0, top: 0, width: 0.25, height: 1, usesStreamFrame: true },
  { left: 0.25, top: 0, width: 0.25, height: 1, usesStreamFrame: true },
  { left: 0, top: 0, width: 1, height: 1, usesStreamFrame: false },
  { left: 0, top: 0, width: 1, height: 1, usesStreamFrame: false },
  { left: 0.5, top: 0, width: 0.25, height: 1, usesStreamFrame: true },
  { left: 0.75, top: 0, width: 0.25, height: 1, usesStreamFrame: true },
];

export type StreamCubeProps = {
  frameBlob: Blob | null;
  imgURL: string | null;
  onContextError?: () => void;
  sceneConfig: SceneConfiguration;
  telemetryValue: number;
};

export function StreamCube({
  frameBlob,
  imgURL,
  onContextError,
  sceneConfig,
  telemetryValue,
}: StreamCubeProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const rendererRef = useRef<WebGLRenderer | null>(null);
  const cameraRef = useRef<PerspectiveCamera | null>(null);
  const cubeRef = useRef<Mesh<BoxGeometry, MeshStandardMaterial[]> | null>(
    null,
  );
  const gridRef = useRef<GridHelper | null>(null);
  const faceTextureRuntimesRef = useRef<FaceTextureRuntime[] | null>(null);
  const animationRef = useRef<number | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const readyFrameRef = useRef<number | null>(null);
  const pendingFrameSourceRef = useRef<Blob | string | null>(
    frameBlob ?? imgURL,
  );
  const isApplyingImageRef = useRef(false);
  const isMountedRef = useRef(true);
  const sceneConfigRef = useRef(sceneConfig);
  const telemetryValueRef = useRef(telemetryValue);
  const [isRendererReady, setIsRendererReady] = useState(false);

  useEffect(() => {
    sceneConfigRef.current = sceneConfig;
  }, [sceneConfig]);

  useEffect(() => {
    telemetryValueRef.current = telemetryValue;
  }, [telemetryValue]);

  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
    };
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;

    if (!container || !canvas) return undefined;

    try {
      const renderer = new WebGLRenderer({
        antialias: true,
        alpha: true,
        canvas,
      });
      renderer.setPixelRatio(window.devicePixelRatio);
      renderer.outputColorSpace = SRGBColorSpace;

      const scene = new Scene();
      scene.background = null;

      const { clientWidth: width, clientHeight: height } = container;
      const camera = new PerspectiveCamera(
        sceneConfigRef.current.camera.fov,
        width / height,
        0.1,
        100,
      );
      camera.position.set(0, 0, sceneConfigRef.current.camera.distance);

      const ambient = new AmbientLight(
        0xffffff,
        sceneConfigRef.current.stage.ambientIntensity,
      );
      const directional = new DirectionalLight(
        0xffffff,
        sceneConfigRef.current.stage.keyIntensity,
      );
      directional.position.set(2, 3, 4);
      scene.add(ambient, directional);

      const grid = new GridHelper(
        GRID_SIZE,
        GRID_DIVISIONS,
        GRID_COLOR,
        GRID_COLOR,
      );
      grid.position.y = GRID_BASELINE_Y;
      applyGridOpacity(grid, sceneConfigRef.current.stage.gridOpacity);
      scene.add(grid);

      const geometry = new BoxGeometry(2, 2, 2);
      const faceTextureRuntimes = createFaceTextureRuntimes(
        sceneConfigRef.current.surface.textureRepeat,
      );
      const materials = faceTextureRuntimes.map(
        ({ texture }) =>
          new MeshStandardMaterial({
            map: texture,
            metalness: sceneConfigRef.current.surface.metalness,
            roughness: sceneConfigRef.current.surface.roughness,
          }),
      );
      const cube = new Mesh(geometry, materials);
      scene.add(cube);

      renderer.setSize(width, height, false);

      rendererRef.current = renderer;
      cameraRef.current = camera;
      cubeRef.current = cube;
      gridRef.current = grid;
      faceTextureRuntimesRef.current = faceTextureRuntimes;
      readyFrameRef.current = window.requestAnimationFrame(() => {
        setIsRendererReady(true);
      });

      const renderFrame = () => {
        const elapsedSeconds = performance.now() / 1000;
        const currentConfig = sceneConfigRef.current;
        const rawTelemetry = currentConfig.telemetry.enabled
          ? Math.tanh(telemetryValueRef.current * currentConfig.telemetry.gain)
          : 0;
        const telemetrySignal = Math.max(
          -MAX_TELEMETRY_SIGNAL,
          Math.min(MAX_TELEMETRY_SIGNAL, rawTelemetry),
        );
        const hoverOffset =
          Math.sin(elapsedSeconds * 0.9) * currentConfig.motion.hoverAmount +
          (currentConfig.telemetry.target === "hover"
            ? telemetrySignal * 0.5
            : 0);
        const wobbleOffset =
          Math.sin(elapsedSeconds * 1.2) * currentConfig.motion.wobbleAmount;
        const telemetryScale =
          currentConfig.telemetry.target === "scale"
            ? 1 + telemetrySignal * 0.22
            : 1;

        if (currentConfig.motion.autoRotate) {
          cube.rotation.x +=
            currentConfig.motion.rotationX +
            (currentConfig.telemetry.target === "rotation"
              ? telemetrySignal * 0.004
              : 0);
          cube.rotation.y +=
            currentConfig.motion.rotationY +
            (currentConfig.telemetry.target === "rotation"
              ? telemetrySignal * 0.006
              : 0);
        } else if (currentConfig.telemetry.target === "rotation") {
          cube.rotation.y += telemetrySignal * 0.008;
        }

        cube.rotation.z = wobbleOffset * 0.3;
        cube.position.y = hoverOffset;
        cube.scale.setScalar(currentConfig.surface.cubeScale * telemetryScale);

        camera.position.z = currentConfig.camera.distance;
        if (camera.fov !== currentConfig.camera.fov) {
          camera.fov = currentConfig.camera.fov;
          camera.updateProjectionMatrix();
        }

        ambient.intensity = currentConfig.stage.ambientIntensity;
        directional.intensity = currentConfig.stage.keyIntensity;
        grid.visible = currentConfig.stage.showGrid;
        grid.position.y = GRID_BASELINE_Y - wobbleOffset * 0.5;
        applyGridOpacity(grid, currentConfig.stage.gridOpacity);
        applySurfaceSettings(cube.material, currentConfig);

        renderer.render(scene, camera);
        animationRef.current = window.requestAnimationFrame(renderFrame);
      };
      renderFrame();

      const handleResize = () => {
        const { clientWidth, clientHeight } = container;
        renderer.setSize(clientWidth, clientHeight, false);
        camera.aspect = clientWidth / clientHeight;
        camera.updateProjectionMatrix();
      };

      const resizeObserver = new ResizeObserver(handleResize);
      resizeObserver.observe(container);
      resizeObserverRef.current = resizeObserver;
    } catch (error) {
      onContextError?.();
      console.error("Failed to initialize WebGL renderer", error);
    }

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
      if (readyFrameRef.current) {
        cancelAnimationFrame(readyFrameRef.current);
      }

      resizeObserverRef.current?.disconnect();

      cubeRef.current?.geometry.dispose();
      cubeRef.current?.material.forEach((material) => {
        material.dispose();
      });

      if (gridRef.current) {
        gridRef.current.geometry.dispose();
        const gridMaterial = gridRef.current.material;
        if (Array.isArray(gridMaterial)) {
          gridMaterial.forEach((material) => material.dispose());
        } else {
          gridMaterial.dispose();
        }
      }

      if (faceTextureRuntimesRef.current) {
        faceTextureRuntimesRef.current.forEach(({ texture }) => {
          texture.dispose();
        });
      }

      rendererRef.current?.dispose();
      rendererRef.current = null;
      cameraRef.current = null;
      cubeRef.current = null;
      gridRef.current = null;
      faceTextureRuntimesRef.current = null;
      resizeObserverRef.current = null;
    };
  }, [onContextError]);

  useEffect(() => {
    pendingFrameSourceRef.current = frameBlob ?? imgURL;

    const applyPendingTexture = async () => {
      if (isApplyingImageRef.current) {
        return;
      }

      isApplyingImageRef.current = true;

      try {
        while (isMountedRef.current) {
          const nextFrameSource = pendingFrameSourceRef.current;
          const faceTextureRuntimes = faceTextureRuntimesRef.current;
          if (!faceTextureRuntimes) {
            return;
          }

          pendingFrameSourceRef.current = null;

          try {
            if (nextFrameSource) {
              const image = await decodeStreamFrame(nextFrameSource);
              try {
                if (!isMountedRef.current) {
                  return;
                }

                const { width, height } = getDecodedFrameSize(image);
                drawFaceTextures(faceTextureRuntimes, image, width, height);
              } finally {
                if (image instanceof ImageBitmap) {
                  image.close();
                }
              }
            } else {
              drawFallbackFaceTextures(faceTextureRuntimes);
            }
          } catch (error) {
            console.warn(
              "Failed to load streamed texture; using fallback",
              error,
            );
            drawFallbackFaceTextures(faceTextureRuntimes);
          }

          faceTextureRuntimes.forEach(({ texture }) => {
            applyTextureSettings(
              texture,
              sceneConfigRef.current.surface.textureRepeat,
            );
            texture.needsUpdate = true;
          });

          if (pendingFrameSourceRef.current === null) {
            return;
          }
        }
      } finally {
        isApplyingImageRef.current = false;
      }
    };

    void applyPendingTexture();
  }, [frameBlob, imgURL]);

  const backgroundTint = Math.round(sceneConfig.stage.backgroundTint * 100);

  return (
    <div
      ref={containerRef}
      className="relative min-h-[240px] w-full flex-1 overflow-hidden rounded-[1.5rem] border border-[#343b45]"
      style={{
        background: `radial-gradient(circle at 20% 20%, rgba(14, 165, 233, ${
          0.08 + backgroundTint / 500
        }), transparent 35%), radial-gradient(circle at 80% 20%, rgba(244, 63, 94, ${
          0.05 + backgroundTint / 700
        }), transparent 28%), linear-gradient(180deg, rgba(15, 23, 42, 0.95), rgba(2, 6, 23, 1))`,
      }}
    >
      <canvas ref={canvasRef} className="size-full" />
      {!isRendererReady && <Skeleton className="absolute inset-0" />}
    </div>
  );
}

function createFaceTextureRuntimes(repeat: number): FaceTextureRuntime[] {
  return CUBE_FACE_VIEWPORTS.map((viewport) => {
    const canvas = document.createElement("canvas");
    canvas.width = STREAM_TEXTURE_SIZE;
    canvas.height = STREAM_TEXTURE_SIZE;
    const context = canvas.getContext("2d");

    if (!context) {
      throw new Error("Failed to create 2D context for stream texture");
    }

    drawFallbackTexture(context, canvas);

    const texture = new CanvasTexture(canvas);
    texture.colorSpace = SRGBColorSpace;
    applyTextureSettings(texture, repeat);
    return { canvas, context, texture, viewport };
  });
}

function drawFallbackTexture(
  context: CanvasRenderingContext2D,
  canvas: HTMLCanvasElement,
) {
  const size = canvas.width;
  context.fillStyle = STREAM_TEXTURE_BACKGROUND;
  context.fillRect(0, 0, size, size);
  const colors = ["#111827", "#1f2937"];
  const squareSize = size / 8;

  for (let y = 0; y < 8; y += 1) {
    for (let x = 0; x < 8; x += 1) {
      context.fillStyle = colors[(x + y) % 2];
      context.fillRect(x * squareSize, y * squareSize, squareSize, squareSize);
    }
  }
}

function applyGridOpacity(grid: GridHelper, opacity: number) {
  const gridMaterial = grid.material;
  if (Array.isArray(gridMaterial)) {
    gridMaterial.forEach((material) => {
      material.transparent = true;
      material.opacity = opacity;
    });
  } else {
    gridMaterial.transparent = true;
    gridMaterial.opacity = opacity;
  }
}

function applySurfaceSettings(
  materials: MeshStandardMaterial[],
  sceneConfig: SceneConfiguration,
) {
  for (const material of materials) {
    material.metalness = sceneConfig.surface.metalness;
    material.roughness = sceneConfig.surface.roughness;
    if (material.map) {
      applyTextureSettings(material.map, sceneConfig.surface.textureRepeat);
    }
  }
}

function applyTextureSettings(texture: Texture, repeat: number) {
  if (texture.userData.repeat === repeat) {
    return;
  }

  texture.wrapS = RepeatWrapping;
  texture.wrapT = RepeatWrapping;
  texture.repeat.set(repeat, repeat);
  texture.userData.repeat = repeat;
  texture.needsUpdate = true;
}

function drawFaceTextures(
  faceTextureRuntimes: FaceTextureRuntime[],
  image: DecodedStreamFrame,
  imageWidth: number,
  imageHeight: number,
) {
  const normalizedStrip = getNormalizedStripRect(imageWidth, imageHeight);

  faceTextureRuntimes.forEach(({ canvas, context, viewport }) => {
    if (!viewport.usesStreamFrame) {
      drawFallbackTexture(context, canvas);
      return;
    }

    context.fillStyle = STREAM_TEXTURE_BACKGROUND;
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(
      image,
      normalizedStrip.left + normalizedStrip.size * 4 * viewport.left,
      normalizedStrip.top + normalizedStrip.size * viewport.top,
      normalizedStrip.size * 4 * viewport.width,
      normalizedStrip.size * viewport.height,
      0,
      0,
      canvas.width,
      canvas.height,
    );
  });
}

export function getNormalizedStripRect(
  imageWidth: number,
  imageHeight: number,
): NormalizedStripRect {
  const squareSize = Math.max(1, Math.min(imageHeight, imageWidth / 4));
  const stripWidth = squareSize * 4;
  const stripHeight = squareSize;

  return {
    left: Math.max(0, (imageWidth - stripWidth) / 2),
    top: Math.max(0, (imageHeight - stripHeight) / 2),
    size: squareSize,
  };
}

function drawFallbackFaceTextures(faceTextureRuntimes: FaceTextureRuntime[]) {
  faceTextureRuntimes.forEach(({ canvas, context }) => {
    drawFallbackTexture(context, canvas);
  });
}

async function decodeStreamFrame(
  source: Blob | string,
): Promise<DecodedStreamFrame> {
  if (typeof createImageBitmap === "function") {
    if (source instanceof Blob) {
      return createImageBitmap(source);
    }

    const response = await fetch(source);
    if (!response.ok) {
      throw new Error(`Failed to fetch stream image: ${source}`);
    }

    return createImageBitmap(await response.blob());
  }

  if (source instanceof Blob) {
    return loadStreamImage(URL.createObjectURL(source), true);
  }

  return loadStreamImage(source);
}

function loadStreamImage(url: string, shouldRevoke = false) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    image.decoding = "async";
    image.onload = () => {
      if (shouldRevoke) {
        URL.revokeObjectURL(url);
      }
      resolve(image);
    };
    image.onerror = () => {
      if (shouldRevoke) {
        URL.revokeObjectURL(url);
      }
      reject(new Error(`Failed to load stream image: ${url}`));
    };
    image.src = url;
  });
}

function getDecodedFrameSize(image: DecodedStreamFrame) {
  if (image instanceof ImageBitmap) {
    return {
      width: image.width,
      height: image.height,
    };
  }

  return {
    width: image.naturalWidth,
    height: image.naturalHeight,
  };
}
