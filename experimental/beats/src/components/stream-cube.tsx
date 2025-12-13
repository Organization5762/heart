import { useEffect, useRef } from "react";
import * as THREE from "three";

import { Skeleton } from "./ui/skeleton";

const CAMERA_DISTANCE = 4;
const ROTATION_DELTA = { x: 0.01, y: 0.015 } as const;

export type StreamCubeProps = {
  imgURL: string | null;
  onContextError?: () => void;
};

export function StreamCube({ imgURL, onContextError }: StreamCubeProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const cubeRef = useRef<THREE.Mesh<THREE.BoxGeometry, THREE.MeshStandardMaterial[]> | null>(
    null,
  );
  const fallbackTextureRef = useRef<THREE.Texture | null>(null);
  const lastTextureRef = useRef<THREE.Texture | null>(null);
  const animationRef = useRef<number | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;

    if (!container || !canvas) return undefined;

    try {
      const renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        canvas,
      });
      renderer.setPixelRatio(window.devicePixelRatio);
      renderer.outputColorSpace = THREE.SRGBColorSpace;

      const scene = new THREE.Scene();
      scene.background = null;

      const { clientWidth: width, clientHeight: height } = container;
      const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 100);
      camera.position.set(0, 0, CAMERA_DISTANCE);

      const ambient = new THREE.AmbientLight(0xffffff, 0.6);
      const directional = new THREE.DirectionalLight(0xffffff, 0.8);
      directional.position.set(2, 3, 4);
      scene.add(ambient, directional);

      const geometry = new THREE.BoxGeometry(2, 2, 2);
      const fallbackTexture = createFallbackTexture();
      const materials = Array.from({ length: 6 }, () =>
        new THREE.MeshStandardMaterial({ map: fallbackTexture }),
      );
      const cube = new THREE.Mesh(geometry, materials);
      scene.add(cube);

      renderer.setSize(width, height, false);

      rendererRef.current = renderer;
      sceneRef.current = scene;
      cameraRef.current = camera;
      cubeRef.current = cube;
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
      fallbackTextureRef.current = null;
      lastTextureRef.current = null;
      resizeObserverRef.current = null;
    };
  }, [onContextError]);

  useEffect(() => {
    let cancelled = false;

    const applyTexture = async () => {
      if (!cubeRef.current || !fallbackTextureRef.current) return;

      let nextTexture: THREE.Texture | null = null;
      try {
        nextTexture = imgURL ? await loadTexture(imgURL) : fallbackTextureRef.current;
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
        if (previousMap && previousMap !== nextTexture && previousMap !== fallbackTextureRef.current) {
          previousMap.dispose();
        }
      });

      if (lastTextureRef.current && lastTextureRef.current !== nextTexture) {
        lastTextureRef.current.dispose();
      }

      lastTextureRef.current = nextTexture === fallbackTextureRef.current ? null : nextTexture;
    };

    applyTexture();

    return () => {
      cancelled = true;
    };
  }, [imgURL]);

  return (
    <div ref={containerRef} className="relative flex-1 min-h-[240px] w-full rounded-md bg-muted/40">
      <canvas ref={canvasRef} className="size-full" />
      {!rendererRef.current && <Skeleton className="absolute inset-0" />}
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

  const colors = ["#111827", "#1f2937"];
  const squareSize = size / 8;

  for (let y = 0; y < 8; y += 1) {
    for (let x = 0; x < 8; x += 1) {
      context.fillStyle = colors[(x + y) % 2];
      context.fillRect(x * squareSize, y * squareSize, squareSize, squareSize);
    }
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(2, 2);

  return texture;
}

function loadTexture(url: string) {
  return new Promise<THREE.Texture>((resolve, reject) => {
    const loader = new THREE.TextureLoader();
    loader.load(
      url,
      (texture) => {
        texture.colorSpace = THREE.SRGBColorSpace;
        resolve(texture);
      },
      undefined,
      (error) => reject(error),
    );
  });
}
