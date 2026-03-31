import { useEffect, useRef } from "react";
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

const CAMERA_DISTANCE = 4;
const ROTATION_DELTA = { x: 0.01, y: 0.015 } as const;
const GRID_SIZE = 6;
const GRID_DIVISIONS = 10;
const GRID_COLOR = 0x2b67ff;
const GRID_OPACITY = 0.26;

export type StreamCubeProps = {
  imgURL: string | null;
  onContextError?: () => void;
};

export function StreamCube({ imgURL, onContextError }: StreamCubeProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const rendererRef = useRef<WebGLRenderer | null>(null);
  const sceneRef = useRef<Scene | null>(null);
  const cameraRef = useRef<PerspectiveCamera | null>(null);
  const cubeRef = useRef<Mesh<BoxGeometry, MeshStandardMaterial[]> | null>(
    null,
  );
  const gridRef = useRef<GridHelper | null>(null);
  const fallbackTextureRef = useRef<Texture | null>(null);
  const lastTextureRef = useRef<Texture | null>(null);
  const animationRef = useRef<number | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

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
      const camera = new PerspectiveCamera(45, width / height, 0.1, 100);
      camera.position.set(0, 0, CAMERA_DISTANCE);

      const ambient = new AmbientLight(0xffffff, 0.6);
      const directional = new DirectionalLight(0xffffff, 0.8);
      directional.position.set(2, 3, 4);
      scene.add(ambient, directional);

      const grid = new GridHelper(
        GRID_SIZE,
        GRID_DIVISIONS,
        GRID_COLOR,
        GRID_COLOR,
      );
      grid.position.y = -1.2;
      const gridMaterial = grid.material;
      if (Array.isArray(gridMaterial)) {
        gridMaterial.forEach((material) => {
          material.transparent = true;
          material.opacity = GRID_OPACITY;
        });
      } else {
        gridMaterial.transparent = true;
        gridMaterial.opacity = GRID_OPACITY;
      }
      scene.add(grid);

      const geometry = new BoxGeometry(2, 2, 2);
      const fallbackTexture = createFallbackTexture();
      const materials = Array.from(
        { length: 6 },
        () => new MeshStandardMaterial({ map: fallbackTexture }),
      );
      const cube = new Mesh(geometry, materials);
      scene.add(cube);

      renderer.setSize(width, height, false);

      rendererRef.current = renderer;
      sceneRef.current = scene;
      cameraRef.current = camera;
      cubeRef.current = cube;
      gridRef.current = grid;
      fallbackTextureRef.current = fallbackTexture;

      const renderFrame = () => {
        cube.rotation.x += ROTATION_DELTA.x;
        cube.rotation.y += ROTATION_DELTA.y;
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
      sceneRef.current = null;
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

  return (
    <div
      ref={containerRef}
      className="relative min-h-[240px] w-full flex-1 overflow-hidden border border-white/20 bg-black/30"
    >
      <Skeleton className="absolute inset-0" />
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(90deg,rgba(43,103,255,0.12)_0,rgba(43,103,255,0.12)_1px,transparent_1px,transparent_52px),linear-gradient(0deg,rgba(43,103,255,0.12)_0,rgba(43,103,255,0.12)_1px,transparent_1px,transparent_52px)] opacity-70" />
      <canvas ref={canvasRef} className="relative size-full" />
    </div>
  );
}

function createFallbackTexture() {
  const size = 128;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");

  if (!context) {
    throw new Error("Failed to create 2D context for fallback texture");
  }

  context.fillStyle = "#070707";
  context.fillRect(0, 0, size, size);

  context.strokeStyle = "rgba(43, 103, 255, 0.45)";
  context.lineWidth = 1;
  for (let index = 0; index <= size; index += 16) {
    context.beginPath();
    context.moveTo(index, 0);
    context.lineTo(index, size);
    context.stroke();

    context.beginPath();
    context.moveTo(0, index);
    context.lineTo(size, index);
    context.stroke();
  }

  context.strokeStyle = "#f2d771";
  context.lineWidth = 3;
  context.strokeRect(10, 10, size - 20, size - 20);

  context.strokeStyle = "#ff5b3a";
  context.lineWidth = 2;
  context.beginPath();
  context.moveTo(18, size - 30);
  context.lineTo(size - 18, 22);
  context.stroke();

  context.strokeStyle = "#6ec2ff";
  context.beginPath();
  context.moveTo(24, 28);
  context.lineTo(size - 34, size - 18);
  context.stroke();

  context.fillStyle = "#f6efe6";
  context.font = '14px "Geist Mono", monospace';
  context.fillText("TX-24", 18, 34);
  context.fillText("U.S.G.C.", 18, size - 18);

  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  texture.wrapS = RepeatWrapping;
  texture.wrapT = RepeatWrapping;
  texture.repeat.set(1.25, 1.25);

  return texture;
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
