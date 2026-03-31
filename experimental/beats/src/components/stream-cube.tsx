import { useEffect, useRef } from "react";
import type { MutableRefObject } from "react";
import {
  ACESFilmicToneMapping,
  AmbientLight,
  BoxGeometry,
  CanvasTexture,
  CircleGeometry,
  Color,
  DirectionalLight,
  EdgesGeometry,
  FogExp2,
  Group,
  LineBasicMaterial,
  LineSegments,
  Material,
  MathUtils,
  Mesh,
  MeshBasicMaterial,
  MeshPhysicalMaterial,
  MeshStandardMaterial,
  PerspectiveCamera,
  PointLight,
  RingGeometry,
  Scene,
  SRGBColorSpace,
  Texture,
  TextureLoader,
  WebGLRenderer,
} from "three";

import { Skeleton } from "./ui/skeleton";

const CAMERA_DISTANCE = 4.8;
const PANEL_WIDTH = 2.6;
const PANEL_HEIGHT = 1.55;
const PANEL_DEPTH = 0.28;
const FLOOR_RADIUS = 4.2;
const RING_INNER_RADIUS = 1.85;
const RING_OUTER_RADIUS = 2.18;

type PointerState = {
  x: number;
  y: number;
};

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
  const stageRef = useRef<Group | null>(null);
  const panelRef = useRef<Mesh<BoxGeometry, Material[]> | null>(null);
  const floorRef = useRef<Mesh<CircleGeometry, MeshBasicMaterial> | null>(null);
  const ringRef = useRef<Mesh<RingGeometry, MeshBasicMaterial> | null>(null);
  const outlineRef = useRef<LineSegments<
    EdgesGeometry,
    LineBasicMaterial
  > | null>(null);
  const accentLightRef = useRef<PointLight | null>(null);
  const screenMaterialsRef = useRef<MeshStandardMaterial[]>([]);
  const disposableMaterialsRef = useRef<Material[]>([]);
  const fallbackTextureRef = useRef<Texture | null>(null);
  const currentTextureRef = useRef<Texture | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);
  const pointerTargetRef = useRef<PointerState>({ x: 0, y: 0 });
  const pointerOffsetRef = useRef<PointerState>({ x: 0, y: 0 });
  const textureRequestIdRef = useRef(0);
  const latestImgUrlRef = useRef(imgURL);

  useEffect(() => {
    latestImgUrlRef.current = imgURL;
  }, [imgURL]);

  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;

    if (!container || !canvas) {
      return undefined;
    }

    let isDisposed = false;

    const handlePointerMove = (event: PointerEvent) => {
      const bounds = container.getBoundingClientRect();
      if (bounds.width === 0 || bounds.height === 0) {
        return;
      }

      pointerTargetRef.current = {
        x: ((event.clientX - bounds.left) / bounds.width) * 2 - 1,
        y: ((event.clientY - bounds.top) / bounds.height) * 2 - 1,
      };
    };

    const handlePointerLeave = () => {
      pointerTargetRef.current = { x: 0, y: 0 };
    };

    try {
      const renderer = new WebGLRenderer({
        alpha: true,
        antialias: true,
        canvas,
        powerPreference: "high-performance",
      });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setClearAlpha(0);
      renderer.outputColorSpace = SRGBColorSpace;
      renderer.toneMapping = ACESFilmicToneMapping;
      renderer.toneMappingExposure = 1.18;

      const scene = new Scene();
      scene.fog = new FogExp2(0x020617, 0.16);

      const { width, height } = getContainerSize(container);
      const camera = new PerspectiveCamera(36, width / height, 0.1, 100);
      camera.position.set(0, 0.35, CAMERA_DISTANCE);

      const stage = new Group();
      scene.add(stage);

      const ambient = new AmbientLight(0xffffff, 0.75);
      const rim = new DirectionalLight(0xffffff, 1.2);
      rim.position.set(-3.5, 2.8, 4.5);
      const fill = new DirectionalLight(0x67e8f9, 0.9);
      fill.position.set(3.2, 1.6, 2.4);
      const accentLight = new PointLight(0x2b67ff, 4.4, 12, 2.2);
      accentLight.position.set(2.1, 0.75, 2.8);
      scene.add(ambient, rim, fill, accentLight);

      const floorMaterial = new MeshBasicMaterial({
        color: 0x070707,
        opacity: 0.92,
        transparent: true,
      });
      const floor = new Mesh(
        new CircleGeometry(FLOOR_RADIUS, 72),
        floorMaterial,
      );
      floor.position.set(0, -1.42, 0);
      floor.rotation.x = -Math.PI / 2;
      scene.add(floor);

      const ringMaterial = new MeshBasicMaterial({
        color: 0xf2d771,
        opacity: 0.12,
        transparent: true,
      });
      const ring = new Mesh(
        new RingGeometry(RING_INNER_RADIUS, RING_OUTER_RADIUS, 72),
        ringMaterial,
      );
      ring.position.set(0, -1.39, 0);
      ring.rotation.x = -Math.PI / 2;
      scene.add(ring);

      const panelGeometry = new BoxGeometry(
        PANEL_WIDTH,
        PANEL_HEIGHT,
        PANEL_DEPTH,
      );
      const fallbackTexture = createFallbackTexture(renderer);
      const chassisMaterial = new MeshPhysicalMaterial({
        clearcoat: 1,
        clearcoatRoughness: 0.18,
        color: 0x111111,
        metalness: 0.72,
        roughness: 0.24,
      });
      const frontMaterial = new MeshStandardMaterial({
        emissive: new Color(0x1d4ed8),
        emissiveIntensity: 0.18,
        map: fallbackTexture,
        metalness: 0.08,
        roughness: 0.22,
      });
      const backMaterial = new MeshStandardMaterial({
        emissive: new Color(0x0f172a),
        emissiveIntensity: 0.08,
        map: fallbackTexture,
        metalness: 0.2,
        roughness: 0.28,
      });
      const panel = new Mesh(panelGeometry, [
        chassisMaterial,
        chassisMaterial,
        chassisMaterial,
        chassisMaterial,
        frontMaterial,
        backMaterial,
      ]);
      panel.position.y = 0.08;
      panel.rotation.x = 0.18;
      panel.rotation.y = -0.55;
      stage.add(panel);

      const outlineMaterial = new LineBasicMaterial({
        color: 0x93c5fd,
        opacity: 0.26,
        transparent: true,
      });
      const outline = new LineSegments(
        new EdgesGeometry(panelGeometry),
        outlineMaterial,
      );
      panel.add(outline);

      renderer.setSize(width, height, false);
      rendererRef.current = renderer;
      sceneRef.current = scene;
      cameraRef.current = camera;
      stageRef.current = stage;
      panelRef.current = panel;
      floorRef.current = floor;
      ringRef.current = ring;
      outlineRef.current = outline;
      accentLightRef.current = accentLight;
      screenMaterialsRef.current = [frontMaterial, backMaterial];
      disposableMaterialsRef.current = [
        chassisMaterial,
        frontMaterial,
        backMaterial,
        floorMaterial,
        ringMaterial,
        outlineMaterial,
      ];
      fallbackTextureRef.current = fallbackTexture;

      const initialTextureRequestId = ++textureRequestIdRef.current;
      void syncScreenTexture({
        currentTextureRef,
        fallbackTexture,
        isCancelled: () =>
          isDisposed || initialTextureRequestId !== textureRequestIdRef.current,
        materials: screenMaterialsRef.current,
        renderer,
        url: latestImgUrlRef.current,
      });

      const handleResize = () => {
        const nextSize = getContainerSize(container);
        renderer.setSize(nextSize.width, nextSize.height, false);
        camera.aspect = nextSize.width / nextSize.height;
        camera.updateProjectionMatrix();
      };

      const renderFrame = (timestamp: number) => {
        const elapsedSeconds = timestamp / 1000;
        const pointerTarget = pointerTargetRef.current;
        const pointerOffset = pointerOffsetRef.current;

        pointerOffset.x = MathUtils.lerp(
          pointerOffset.x,
          pointerTarget.x,
          0.08,
        );
        pointerOffset.y = MathUtils.lerp(
          pointerOffset.y,
          pointerTarget.y,
          0.08,
        );

        const targetRotationX =
          0.22 +
          Math.sin(elapsedSeconds * 0.58) * 0.11 -
          pointerOffset.y * 0.16;
        const targetRotationY =
          -0.58 + elapsedSeconds * 0.28 + pointerOffset.x * 0.24;

        panel.rotation.x = MathUtils.lerp(
          panel.rotation.x,
          targetRotationX,
          0.08,
        );
        panel.rotation.y = MathUtils.lerp(
          panel.rotation.y,
          targetRotationY,
          0.08,
        );
        panel.rotation.z =
          Math.sin(elapsedSeconds * 0.36) * 0.035 + pointerOffset.x * 0.04;

        stage.position.y = Math.sin(elapsedSeconds * 0.88) * 0.08;
        stage.position.x = pointerOffset.x * 0.08;

        camera.position.x =
          Math.sin(elapsedSeconds * 0.24) * 0.4 + pointerOffset.x * 0.34;
        camera.position.y =
          0.28 +
          Math.cos(elapsedSeconds * 0.33) * 0.16 -
          pointerOffset.y * 0.22;
        camera.position.z =
          CAMERA_DISTANCE + Math.sin(elapsedSeconds * 0.22) * 0.12;
        camera.lookAt(0, 0.08, 0);

        accentLight.position.x = Math.cos(elapsedSeconds * 0.72) * 2.4;
        accentLight.position.y = 0.5 + Math.sin(elapsedSeconds * 0.45) * 0.35;
        accentLight.position.z = 2.6 + Math.sin(elapsedSeconds * 0.53) * 0.4;

        ring.material.opacity =
          0.08 + (Math.sin(elapsedSeconds * 1.4) + 1) * 0.03;
        outline.material.opacity =
          0.22 + (Math.cos(elapsedSeconds * 1.1) + 1) * 0.03;

        renderer.render(scene, camera);
        animationFrameRef.current = window.requestAnimationFrame(renderFrame);
      };

      const resizeObserver = new ResizeObserver(handleResize);
      resizeObserver.observe(container);
      resizeObserverRef.current = resizeObserver;

      container.addEventListener("pointermove", handlePointerMove);
      container.addEventListener("pointerleave", handlePointerLeave);

      animationFrameRef.current = window.requestAnimationFrame(renderFrame);
    } catch (error) {
      onContextError?.();
      console.error("Failed to initialize WebGL renderer", error);
    }

    return () => {
      isDisposed = true;
      textureRequestIdRef.current += 1;

      if (animationFrameRef.current) {
        window.cancelAnimationFrame(animationFrameRef.current);
      }

      resizeObserverRef.current?.disconnect();
      container.removeEventListener("pointermove", handlePointerMove);
      container.removeEventListener("pointerleave", handlePointerLeave);

      currentTextureRef.current?.dispose();
      fallbackTextureRef.current?.dispose();

      outlineRef.current?.geometry.dispose();
      panelRef.current?.geometry.dispose();
      floorRef.current?.geometry.dispose();
      ringRef.current?.geometry.dispose();

      disposableMaterialsRef.current.forEach((material) => material.dispose());
      rendererRef.current?.dispose();

      rendererRef.current = null;
      sceneRef.current = null;
      cameraRef.current = null;
      stageRef.current = null;
      panelRef.current = null;
      floorRef.current = null;
      ringRef.current = null;
      outlineRef.current = null;
      accentLightRef.current = null;
      screenMaterialsRef.current = [];
      disposableMaterialsRef.current = [];
      fallbackTextureRef.current = null;
      currentTextureRef.current = null;
      resizeObserverRef.current = null;
      pointerTargetRef.current = { x: 0, y: 0 };
      pointerOffsetRef.current = { x: 0, y: 0 };
    };
  }, [onContextError]);

  useEffect(() => {
    const renderer = rendererRef.current;
    const fallbackTexture = fallbackTextureRef.current;
    const materials = screenMaterialsRef.current;

    if (!renderer || !fallbackTexture || materials.length === 0) {
      return undefined;
    }

    let isCancelled = false;
    const requestId = ++textureRequestIdRef.current;

    void syncScreenTexture({
      currentTextureRef,
      fallbackTexture,
      isCancelled: () =>
        isCancelled || requestId !== textureRequestIdRef.current,
      materials,
      renderer,
      url: imgURL,
    });

    return () => {
      isCancelled = true;
    };
  }, [imgURL]);

  return (
    <div
      ref={containerRef}
      className="relative min-h-[260px] w-full flex-1 overflow-hidden border border-white/20 bg-[radial-gradient(circle_at_top,rgba(43,103,255,0.2),transparent_34%),radial-gradient(circle_at_bottom,rgba(242,215,113,0.08),transparent_42%),linear-gradient(180deg,rgba(7,7,7,0.96),rgba(2,6,23,0.98))] shadow-[0_24px_80px_rgba(2,6,23,0.55)]"
    >
      <Skeleton className="absolute inset-0 rounded-none" />
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,transparent,rgba(14,165,233,0.08)_58%,rgba(2,6,23,0.72))]" />
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(90deg,rgba(43,103,255,0.12)_0,rgba(43,103,255,0.12)_1px,transparent_1px,transparent_52px),linear-gradient(0deg,rgba(43,103,255,0.12)_0,rgba(43,103,255,0.12)_1px,transparent_1px,transparent_52px)] opacity-70" />
      <canvas ref={canvasRef} className="relative size-full" />
    </div>
  );
}

function getContainerSize(container: HTMLDivElement) {
  return {
    height: Math.max(container.clientHeight, 1),
    width: Math.max(container.clientWidth, 1),
  };
}

function configureTexture(texture: Texture, renderer: WebGLRenderer) {
  texture.anisotropy = renderer.capabilities.getMaxAnisotropy();
  texture.colorSpace = SRGBColorSpace;
}

function commitScreenTexture({
  currentTextureRef,
  fallbackTexture,
  materials,
  nextTexture,
}: {
  currentTextureRef: MutableRefObject<Texture | null>;
  fallbackTexture: Texture;
  materials: MeshStandardMaterial[];
  nextTexture: Texture;
}) {
  const staleTextures = new Set<Texture>();

  materials.forEach((material, index) => {
    const previousMap = material.map;
    material.map = nextTexture;
    material.emissiveIntensity = index === 0 ? 0.18 : 0.08;
    material.needsUpdate = true;

    if (
      previousMap &&
      previousMap !== nextTexture &&
      previousMap !== fallbackTexture
    ) {
      staleTextures.add(previousMap);
    }
  });

  staleTextures.forEach((texture) => {
    if (texture !== currentTextureRef.current) {
      texture.dispose();
    }
  });

  if (
    currentTextureRef.current &&
    currentTextureRef.current !== nextTexture &&
    currentTextureRef.current !== fallbackTexture
  ) {
    currentTextureRef.current.dispose();
  }

  currentTextureRef.current =
    nextTexture === fallbackTexture ? null : nextTexture;
}

async function syncScreenTexture({
  currentTextureRef,
  fallbackTexture,
  isCancelled,
  materials,
  renderer,
  url,
}: {
  currentTextureRef: MutableRefObject<Texture | null>;
  fallbackTexture: Texture;
  isCancelled: () => boolean;
  materials: MeshStandardMaterial[];
  renderer: WebGLRenderer;
  url: string | null;
}) {
  let nextTexture: Texture | null = null;

  try {
    nextTexture = url ? await loadTexture(url, renderer) : fallbackTexture;
  } catch (error) {
    console.warn("Falling back to the placeholder stream texture", error);
    nextTexture = fallbackTexture;
  }

  if (isCancelled() || !nextTexture) {
    if (nextTexture && nextTexture !== fallbackTexture) {
      nextTexture.dispose();
    }
    return;
  }

  commitScreenTexture({
    currentTextureRef,
    fallbackTexture,
    materials,
    nextTexture,
  });
}

function createFallbackTexture(renderer: WebGLRenderer) {
  const size = 512;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext("2d");

  if (!context) {
    throw new Error("Failed to create 2D context for fallback texture");
  }

  const background = context.createLinearGradient(0, 0, size, size);
  background.addColorStop(0, "#070707");
  background.addColorStop(0.58, "#0f172a");
  background.addColorStop(1, "#173781");
  context.fillStyle = background;
  context.fillRect(0, 0, size, size);

  context.strokeStyle = "rgba(43, 103, 255, 0.26)";
  context.lineWidth = 1;
  const gridStep = size / 12;
  for (let line = gridStep; line < size; line += gridStep) {
    context.beginPath();
    context.moveTo(line, 0);
    context.lineTo(line, size);
    context.stroke();

    context.beginPath();
    context.moveTo(0, line);
    context.lineTo(size, line);
    context.stroke();
  }

  context.fillStyle = "rgba(7, 7, 7, 0.78)";
  context.fillRect(72, 88, size - 144, size - 176);

  context.strokeStyle = "rgba(242, 215, 113, 0.9)";
  context.lineWidth = 10;
  context.strokeRect(72, 88, size - 144, size - 176);

  context.strokeStyle = "rgba(255, 91, 58, 0.9)";
  context.lineWidth = 6;
  context.beginPath();
  context.moveTo(108, size - 122);
  context.lineTo(size - 112, 136);
  context.stroke();

  context.strokeStyle = "rgba(110, 194, 255, 0.92)";
  context.beginPath();
  context.moveTo(124, 152);
  context.lineTo(size - 136, size - 118);
  context.stroke();

  context.fillStyle = "#f6efe6";
  context.font = '700 22px "Geist Mono", monospace';
  context.fillText("UNITED STATES GRAPHICS COMPANY", 96, 132);

  context.fillStyle = "#f2d771";
  context.font = '700 34px "Tomorrow", sans-serif';
  context.fillText("TR-100 / WAITING FOR STREAM", 96, 204);

  context.fillStyle = "#d6cec3";
  context.font = '500 20px "Geist Mono", monospace';
  context.fillText("Surface feed is online once a frame arrives.", 96, 252);
  context.fillText("Fallback texture doubles as machine report.", 96, 286);
  context.fillText("Signal path: ws://localhost:8765", 96, 320);

  const texture = new CanvasTexture(canvas);
  configureTexture(texture, renderer);
  return texture;
}

function loadTexture(url: string, renderer: WebGLRenderer) {
  return new Promise<Texture>((resolve, reject) => {
    const loader = new TextureLoader();
    loader.load(
      url,
      (texture) => {
        configureTexture(texture, renderer);
        resolve(texture);
      },
      undefined,
      (error) => reject(error),
    );
  });
}
