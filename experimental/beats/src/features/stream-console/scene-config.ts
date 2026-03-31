export type TelemetryTarget = "rotation" | "hover" | "scale";

export type SceneConfiguration = {
  motion: {
    autoRotate: boolean;
    rotationX: number;
    rotationY: number;
    wobbleAmount: number;
    hoverAmount: number;
  };
  camera: {
    distance: number;
    fov: number;
  };
  stage: {
    showGrid: boolean;
    gridOpacity: number;
    ambientIntensity: number;
    keyIntensity: number;
    backgroundTint: number;
  };
  surface: {
    cubeScale: number;
    textureRepeat: number;
    metalness: number;
    roughness: number;
  };
  telemetry: {
    enabled: boolean;
    sensorId: string | null;
    gain: number;
    target: TelemetryTarget;
  };
};

export const DEFAULT_SCENE_CONFIGURATION: SceneConfiguration = {
  motion: {
    autoRotate: false,
    rotationX: 0.01,
    rotationY: 0.015,
    wobbleAmount: 0.12,
    hoverAmount: 0.18,
  },
  camera: {
    distance: 4.9,
    fov: 45,
  },
  stage: {
    showGrid: true,
    gridOpacity: 0.18,
    ambientIntensity: 0.6,
    keyIntensity: 0.8,
    backgroundTint: 0.35,
  },
  surface: {
    cubeScale: 1,
    textureRepeat: 2,
    metalness: 0.08,
    roughness: 0.72,
  },
  telemetry: {
    enabled: true,
    sensorId: null,
    gain: 0.08,
    target: "hover",
  },
};
