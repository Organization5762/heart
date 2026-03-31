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
  TextureLoader,
  WebGLRenderer,
} from "three";

import { Skeleton } from "./ui/skeleton";

const GRID_SIZE = 6;
const GRID_DIVISIONS = 10;
const GRID_COLOR = 0xffffff;
const GRID_BASELINE_Y = -1.2;
const MAX_TELEMETRY_SIGNAL = 1;

export type StreamCubeProps = {
  imgURL: string | null;
  onContextError?: () => void;
  sceneConfig: SceneConfiguration;
  telemetryValue: number;
};

export function StreamCube({
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
  const fallbackTextureRef = useRef<Texture | null>(null);
  const lastTextureRef = useRef<Texture | null>(null);
  const animationRef = useRef<number | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const readyFrameRef = useRef<number | null>(null);
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
      const fallbackTexture = createFallbackTexture(
        sceneConfigRef.current.surface.textureRepeat,
      );
      const materials = Array.from(
        { length: 6 },
        () =>
          new MeshStandardMaterial({
            map: fallbackTexture,
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
      fallbackTextureRef.current = fallbackTexture;
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
        if (material.map && material.map !== fallbackTextureRef.current) {
          material.map.dispose();
        }
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

      if (fallbackTextureRef.current) {
        fallbackTextureRef.current.dispose();
      }

      if (lastTextureRef.current) {
        lastTextureRef.current.dispose();
      }

      rendererRef.current?.dispose();
      rendererRef.current = null;
      cameraRef.current = null;
      cubeRef.current = null;
      gridRef.current = null;
      fallbackTextureRef.current = null;
      lastTextureRef.current = null;
      resizeObserverRef.current = null;
    };
  }, [onContextError]);

  useEffect(() => {
    let cancelled = false;

    const applyTexture = async () => {
      if (!cubeRef.current || !fallbackTextureRef.current) return;

      let nextTexture: Texture | null = null;
      try {
        nextTexture = imgURL
          ? await loadTexture(imgURL)
          : fallbackTextureRef.current;
        if (nextTexture) {
          applyTextureSettings(
            nextTexture,
            sceneConfigRef.current.surface.textureRepeat,
          );
        }
      } catch (error) {
        console.warn("Failed to load streamed texture; using fallback", error);
        nextTexture = fallbackTextureRef.current;
      }

      if (cancelled || !cubeRef.current || !nextTexture) {
        if (nextTexture && nextTexture !== fallbackTextureRef.current) {
          nextTexture.dispose();
        }
        return;
      }

      const materials = cubeRef.current.material;
      materials.forEach((material) => {
        const previousMap = material.map;
        material.map = nextTexture;
        material.needsUpdate = true;
        if (
          previousMap &&
          previousMap !== nextTexture &&
          previousMap !== fallbackTextureRef.current
        ) {
          previousMap.dispose();
        }
      });

      if (lastTextureRef.current && lastTextureRef.current !== nextTexture) {
        lastTextureRef.current.dispose();
      }

      lastTextureRef.current =
        nextTexture === fallbackTextureRef.current ? null : nextTexture;
    };

    applyTexture();

    return () => {
      cancelled = true;
    };
  }, [imgURL]);

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

function createFallbackTexture(repeat: number) {
  const size = 128;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");

  if (!context) {
    throw new Error("Failed to create 2D context for fallback texture");
  }

  const colors = ["#111827", "#1f2937"];
  const squareSize = size / 8;

  for (let y = 0; y < 8; y += 1) {
    for (let x = 0; x < 8; x += 1) {
      context.fillStyle = colors[(x + y) % 2];
      context.fillRect(x * squareSize, y * squareSize, squareSize, squareSize);
    }
  }

  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  applyTextureSettings(texture, repeat);

  return texture;
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

function loadTexture(url: string) {
  return new Promise<Texture>((resolve, reject) => {
    const loader = new TextureLoader();
    loader.load(
      url,
      (texture) => {
        texture.colorSpace = SRGBColorSpace;
        resolve(texture);
      },
      undefined,
      (error) => reject(error),
    );
  });
}
