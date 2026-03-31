import { useEffect, useRef, useState } from "react";
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
  const hasRenderedFrameRef = useRef(false);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;

    if (!container || !canvas) {
      return undefined;
    }

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
      const accentLight = new PointLight(0x38bdf8, 4.4, 12, 2.2);
      accentLight.position.set(2.1, 0.75, 2.8);
      scene.add(ambient, rim, fill, accentLight);

      const floorMaterial = new MeshBasicMaterial({
        color: 0x0f172a,
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
        color: 0x38bdf8,
        opacity: 0.14,
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
        color: 0x0f172a,
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
          0.1 + (Math.sin(elapsedSeconds * 1.4) + 1) * 0.03;
        outline.material.opacity =
          0.22 + (Math.cos(elapsedSeconds * 1.1) + 1) * 0.03;

        if (!hasRenderedFrameRef.current) {
          hasRenderedFrameRef.current = true;
          setIsReady(true);
        }

        renderer.render(scene, camera);
        animationFrameRef.current = window.requestAnimationFrame(renderFrame);
      };

      const resizeObserver = new ResizeObserver(handleResize);
      resizeObserver.observe(container);
      resizeObserverRef.current = resizeObserver;

      container.addEventListener("pointermove", handlePointerMove);
      container.addEventListener("pointerleave", handlePointerLeave);

      animationFrameRef.current = window.requestAnimationFrame(renderFrame);

      return () => {
        if (animationFrameRef.current) {
          window.cancelAnimationFrame(animationFrameRef.current);
        }

        resizeObserver.disconnect();
        container.removeEventListener("pointermove", handlePointerMove);
        container.removeEventListener("pointerleave", handlePointerLeave);

        currentTextureRef.current?.dispose();
        fallbackTextureRef.current?.dispose();

        outline.geometry.dispose();
        panel.geometry.dispose();
        floor.geometry.dispose();
        ring.geometry.dispose();

        disposableMaterialsRef.current.forEach((material) =>
          material.dispose(),
        );
        renderer.dispose();

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
        hasRenderedFrameRef.current = false;
      };
    } catch (error) {
      onContextError?.();
      console.error("Failed to initialize WebGL renderer", error);
    }

    return undefined;
  }, [onContextError]);

  useEffect(() => {
    let isCancelled = false;

    const applyTexture = async () => {
      const renderer = rendererRef.current;
      const fallbackTexture = fallbackTextureRef.current;
      const materials = screenMaterialsRef.current;

      if (!renderer || !fallbackTexture || materials.length === 0) {
        return;
      }

      let nextTexture: Texture | null = null;
      try {
        nextTexture = imgURL
          ? await loadTexture(imgURL, renderer)
          : fallbackTexture;
      } catch (error) {
        console.warn("Falling back to the placeholder stream texture", error);
        nextTexture = fallbackTexture;
      }

      if (isCancelled || !nextTexture) {
        if (nextTexture !== fallbackTexture) {
          nextTexture?.dispose();
        }
        return;
      }

      materials.forEach((material, index) => {
        material.map = nextTexture;
        material.emissiveIntensity = index === 0 ? 0.18 : 0.08;
        material.needsUpdate = true;
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
    };

    void applyTexture();

    return () => {
      isCancelled = true;
    };
  }, [imgURL, isReady]);

  return (
    <div
      ref={containerRef}
      className="border-border/60 relative min-h-[260px] w-full flex-1 overflow-hidden rounded-xl border bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.18),transparent_34%),radial-gradient(circle_at_bottom,rgba(14,165,233,0.14),transparent_42%),linear-gradient(180deg,rgba(15,23,42,0.94),rgba(2,6,23,0.98))] shadow-[0_24px_80px_rgba(2,6,23,0.55)]"
    >
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,transparent,rgba(14,165,233,0.08)_58%,rgba(2,6,23,0.72))]" />
      <canvas ref={canvasRef} className="relative size-full" />
      {!isReady && <Skeleton className="absolute inset-0 rounded-none" />}
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
  background.addColorStop(0, "#020617");
  background.addColorStop(0.55, "#0f172a");
  background.addColorStop(1, "#1d4ed8");
  context.fillStyle = background;
  context.fillRect(0, 0, size, size);

  context.strokeStyle = "rgba(148, 163, 184, 0.14)";
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

  context.fillStyle = "rgba(15, 23, 42, 0.72)";
  context.fillRect(92, 116, size - 184, size - 232);
  context.strokeStyle = "rgba(125, 211, 252, 0.72)";
  context.lineWidth = 12;
  context.strokeRect(92, 116, size - 184, size - 232);

  context.fillStyle = "#e2e8f0";
  context.font = "700 42px sans-serif";
  context.fillText("WAITING FOR STREAM", 118, 252);

  context.strokeStyle = "rgba(125, 211, 252, 0.9)";
  context.lineWidth = 8;
  context.beginPath();
  context.moveTo(126, 334);
  context.bezierCurveTo(166, 276, 216, 388, 266, 318);
  context.bezierCurveTo(306, 272, 344, 364, 390, 326);
  context.bezierCurveTo(426, 300, 456, 332, 486, 316);
  context.stroke();

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
