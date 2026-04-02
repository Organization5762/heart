import type {
  PeripheralInfo,
  PeripheralTag,
} from "@/actions/ws/providers/PeripheralProvider";

const MATH_SCOPE = {
  PI: Math.PI,
  E: Math.E,
  abs: Math.abs,
  ceil: Math.ceil,
  clamp: (value: number, min: number, max: number) =>
    Math.min(max, Math.max(min, value)),
  cos: Math.cos,
  exp: Math.exp,
  floor: Math.floor,
  log: Math.log,
  max: Math.max,
  min: Math.min,
  mix: (start: number, end: number, amount: number) =>
    start + (end - start) * amount,
  pow: Math.pow,
  pulse: (timeSeconds: number, periodSeconds: number, dutyCycle = 0.5) => {
    if (periodSeconds <= 0) {
      return 0;
    }
    const cycle =
      ((timeSeconds % periodSeconds) + periodSeconds) % periodSeconds;
    return cycle / periodSeconds <= dutyCycle ? 1 : 0;
  },
  round: Math.round,
  saw: (timeSeconds: number, periodSeconds = 1) => {
    if (periodSeconds <= 0) {
      return 0;
    }
    const cycle =
      ((timeSeconds % periodSeconds) + periodSeconds) % periodSeconds;
    return cycle / periodSeconds;
  },
  sin: Math.sin,
  smoothstep: (edge0: number, edge1: number, x: number) => {
    if (edge0 === edge1) {
      return 0;
    }
    const normalized = Math.min(1, Math.max(0, (x - edge0) / (edge1 - edge0)));
    return normalized * normalized * (3 - 2 * normalized);
  },
  sqrt: Math.sqrt,
  tan: Math.tan,
  triangle: (timeSeconds: number, periodSeconds = 1) => {
    if (periodSeconds <= 0) {
      return 0;
    }
    const cycle =
      ((timeSeconds % periodSeconds) + periodSeconds) % periodSeconds;
    const normalized = cycle / periodSeconds;
    return 1 - Math.abs(normalized * 2 - 1);
  },
};

const MATH_SCOPE_KEYS = Object.keys(MATH_SCOPE);
const MATH_SCOPE_VALUES = Object.values(MATH_SCOPE);

export const SENSOR_FUNCTION_PRESETS = [
  {
    label: "Breath",
    expression: "0.4 + 0.2 * sin(t * 1.25)",
  },
  {
    label: "Pulse",
    expression: "pulse(t, 1.5, 0.18)",
  },
  {
    label: "Sweep",
    expression: "triangle(t, 8)",
  },
];

const DEFAULT_FAKE_PERIPHERAL_ID = "fake.peripheral";
const DEFAULT_FAKE_PERIPHERAL_LABEL = "Fake Peripheral";
const TOTEM_SENSOR_PERIPHERAL_ID = "totem.sensor";
const ACCELEROMETER_DEBUG_PERIPHERAL_ID = "accelerometer:debug";

type FakeSensorDefinition = {
  path: string;
  tags?: PeripheralTag[];
  controlKeys: string[];
};

const DEFAULT_FAKE_SENSOR_TAGS: PeripheralTag[] = [
  {
    name: "input_variant",
    variant: "fake_peripheral",
  },
  {
    name: "mode",
    variant: "virtual",
  },
];

const DEFAULT_FAKE_PERIPHERAL_SENSORS: FakeSensorDefinition[] = [
  {
    path: "payload.motion.accelerometer.x",
    controlKeys: [
      `${ACCELEROMETER_DEBUG_PERIPHERAL_ID}:x`,
      `${TOTEM_SENSOR_PERIPHERAL_ID}:payload.motion.accelerometer.x`,
    ],
  },
  {
    path: "payload.motion.accelerometer.y",
    controlKeys: [
      `${ACCELEROMETER_DEBUG_PERIPHERAL_ID}:y`,
      `${TOTEM_SENSOR_PERIPHERAL_ID}:payload.motion.accelerometer.y`,
    ],
  },
  {
    path: "payload.motion.accelerometer.z",
    controlKeys: [
      `${ACCELEROMETER_DEBUG_PERIPHERAL_ID}:z`,
      `${TOTEM_SENSOR_PERIPHERAL_ID}:payload.motion.accelerometer.z`,
    ],
  },
  {
    path: "payload.gamepad.dpad.up",
    controlKeys: [`${TOTEM_SENSOR_PERIPHERAL_ID}:payload.gamepad.dpad.up`],
  },
  {
    path: "payload.gamepad.dpad.down",
    controlKeys: [`${TOTEM_SENSOR_PERIPHERAL_ID}:payload.gamepad.dpad.down`],
  },
  {
    path: "payload.gamepad.dpad.left",
    controlKeys: [`${TOTEM_SENSOR_PERIPHERAL_ID}:payload.gamepad.dpad.left`],
  },
  {
    path: "payload.gamepad.dpad.right",
    controlKeys: [`${TOTEM_SENSOR_PERIPHERAL_ID}:payload.gamepad.dpad.right`],
  },
  {
    path: "payload.gamepad.buttons.primary",
    controlKeys: [
      `${TOTEM_SENSOR_PERIPHERAL_ID}:payload.gamepad.buttons.primary`,
    ],
  },
  {
    path: "payload.gamepad.buttons.secondary",
    controlKeys: [
      `${TOTEM_SENSOR_PERIPHERAL_ID}:payload.gamepad.buttons.secondary`,
    ],
  },
  {
    path: "payload.gamepad.buttons.menu",
    controlKeys: [`${TOTEM_SENSOR_PERIPHERAL_ID}:payload.gamepad.buttons.menu`],
  },
  {
    path: "payload.gamepad.triggers.left",
    controlKeys: [
      `${TOTEM_SENSOR_PERIPHERAL_ID}:payload.gamepad.triggers.left`,
    ],
  },
  {
    path: "payload.gamepad.triggers.right",
    controlKeys: [
      `${TOTEM_SENSOR_PERIPHERAL_ID}:payload.gamepad.triggers.right`,
    ],
  },
];

export type LivePeripheralSnapshot = {
  ts: number;
  info: PeripheralInfo;
  last_data: unknown;
};

export type SensorSource = "live" | "fake";

export type SensorChannel = {
  id: string;
  commandKey: string;
  controlKeys: string[];
  peripheralId: string;
  peripheralLabel: string;
  label: string;
  leafLabel: string;
  path: string;
  pathSegments: string[];
  value: number | null;
  rawValue: number | boolean | null;
  displayValue: string;
  hasLiveValue: boolean;
  updatedAt: number;
  tags: PeripheralTag[];
  source: SensorSource;
};

export type SensorOverrideMode = "live" | "constant" | "function";

export type SensorOverride = {
  mode: SensorOverrideMode;
  constantValue: number;
  expression: string;
};

export type ResolvedSensorChannel = SensorChannel & {
  effectiveValue: number;
  referenceValue: number | null;
  evaluationError: string | null;
};

export type SensorHistoryPoint = {
  timeSeconds: number;
  liveValue: number | null;
  effectiveValue: number;
  referenceValue: number | null;
};

export function defaultSensorOverride(): SensorOverride {
  return {
    mode: "live",
    constantValue: 0,
    expression: SENSOR_FUNCTION_PRESETS[0].expression,
  };
}

export function extractSensorChannels(
  peripherals: Record<string, LivePeripheralSnapshot>,
): SensorChannel[] {
  const liveChannels = Object.values(peripherals).flatMap((snapshot) =>
    flattenLiveSensorPayload(snapshot.info, snapshot.last_data, snapshot.ts),
  );
  const fakeChannels = buildFakeSensorChannels();
  const channels = mergeSensorChannels(liveChannels, fakeChannels);

  return channels.sort((left, right) => left.label.localeCompare(right.label));
}

export function compileSensorExpression(expression: string) {
  if (!expression.trim()) {
    return {
      evaluate: null,
      error: "Enter a function that returns a numeric value.",
    };
  }

  try {
    const compiled = new Function(
      "t",
      ...MATH_SCOPE_KEYS,
      `"use strict"; return (${expression});`,
    ) as (...args: unknown[]) => unknown;

    return {
      evaluate: (timeSeconds: number) => {
        const result = compiled(timeSeconds, ...MATH_SCOPE_VALUES);
        if (typeof result !== "number" || !Number.isFinite(result)) {
          throw new Error("The function must return a finite number.");
        }
        return result;
      },
      error: null,
    };
  } catch (error) {
    return {
      evaluate: null,
      error:
        error instanceof Error
          ? error.message
          : "Unable to compile expression.",
    };
  }
}

export function resolveSensorChannel(
  sensor: SensorChannel,
  override: SensorOverride | undefined,
  timeSeconds: number,
): ResolvedSensorChannel {
  if (!override || override.mode === "live") {
    return {
      ...sensor,
      effectiveValue: sensor.value ?? 0,
      referenceValue: null,
      evaluationError: null,
    };
  }

  if (override.mode === "constant") {
    return {
      ...sensor,
      effectiveValue: override.constantValue,
      referenceValue: override.constantValue,
      evaluationError: null,
    };
  }

  const compiled = compileSensorExpression(override.expression);
  if (!compiled.evaluate) {
    return {
      ...sensor,
      effectiveValue: sensor.value ?? 0,
      referenceValue: null,
      evaluationError: compiled.error,
    };
  }

  try {
    const nextValue = compiled.evaluate(timeSeconds);
    return {
      ...sensor,
      effectiveValue: nextValue,
      referenceValue: nextValue,
      evaluationError: null,
    };
  } catch (error) {
    return {
      ...sensor,
      effectiveValue: sensor.value ?? 0,
      referenceValue: null,
      evaluationError:
        error instanceof Error
          ? error.message
          : "Unable to evaluate expression.",
    };
  }
}

export function appendSensorHistory(
  history: SensorHistoryPoint[],
  nextPoint: SensorHistoryPoint,
  limit: number,
) {
  const nextHistory = [...history, nextPoint];
  if (nextHistory.length <= limit) {
    return nextHistory;
  }
  return nextHistory.slice(nextHistory.length - limit);
}

export function formatSensorValue(value: number | null, digits = 3) {
  if (value === null || Number.isNaN(value)) {
    return "n/a";
  }
  return value.toFixed(digits);
}

function flattenLiveSensorPayload(
  peripheral: PeripheralInfo,
  value: unknown,
  timestamp: number,
) {
  const peripheralId = peripheral.id ?? "unknown";
  const entries = collectNumericEntries(value);

  return entries.map(({ path, numericValue, rawValue }) => {
    const pathSegments = path.length === 0 ? ["value"] : path;
    const pathLabel = pathSegments.join(".");
    const label = `${peripheralId} / ${pathLabel}`;

    return {
      id: label,
      commandKey: `${peripheralId}:${pathLabel}`,
      controlKeys: [`${peripheralId}:${pathLabel}`],
      peripheralId,
      peripheralLabel: peripheralId,
      label,
      leafLabel: pathSegments[pathSegments.length - 1] ?? pathLabel,
      path: pathLabel,
      pathSegments,
      value: numericValue,
      rawValue,
      displayValue:
        typeof rawValue === "boolean"
          ? String(rawValue)
          : numericValue.toFixed(3),
      hasLiveValue: true,
      updatedAt: timestamp,
      tags: peripheral.tags,
      source: "live" as const,
    };
  });
}

function buildFakeSensorChannels(): SensorChannel[] {
  return DEFAULT_FAKE_PERIPHERAL_SENSORS.map((sensor, index) => {
    const pathSegments = sensor.path.split(".");
    const label = `${DEFAULT_FAKE_PERIPHERAL_LABEL} / ${sensor.path}`;

    return {
      id: `${DEFAULT_FAKE_PERIPHERAL_ID}/${sensor.path}`,
      commandKey: `${DEFAULT_FAKE_PERIPHERAL_ID}:${sensor.path}`,
      controlKeys: sensor.controlKeys,
      peripheralId: DEFAULT_FAKE_PERIPHERAL_ID,
      peripheralLabel: DEFAULT_FAKE_PERIPHERAL_LABEL,
      label,
      leafLabel: pathSegments[pathSegments.length - 1] ?? sensor.path,
      path: sensor.path,
      pathSegments,
      value: null,
      rawValue: null,
      displayValue: "Idle",
      hasLiveValue: false,
      updatedAt: index,
      tags: sensor.tags ?? DEFAULT_FAKE_SENSOR_TAGS,
      source: "fake",
    };
  });
}

function mergeSensorChannels(
  liveChannels: SensorChannel[],
  fallbackChannels: SensorChannel[],
) {
  const byCommandKey = new Map(
    fallbackChannels.map((channel) => [channel.commandKey, channel]),
  );

  liveChannels.forEach((channel) => {
    byCommandKey.set(channel.commandKey, channel);
  });

  return Array.from(byCommandKey.values());
}

function collectNumericEntries(
  value: unknown,
  path: string[] = [],
): Array<{
  path: string[];
  numericValue: number;
  rawValue: number | boolean;
}> {
  if (typeof value === "number" && Number.isFinite(value)) {
    return [
      {
        path,
        numericValue: value,
        rawValue: value,
      },
    ];
  }

  if (typeof value === "boolean") {
    return [
      {
        path,
        numericValue: value ? 1 : 0,
        rawValue: value,
      },
    ];
  }

  if (Array.isArray(value)) {
    return value.flatMap((entry, index) =>
      collectNumericEntries(entry, [...path, String(index)]),
    );
  }

  if (value && typeof value === "object") {
    return Object.entries(value as Record<string, unknown>).flatMap(
      ([key, entry]) => collectNumericEntries(entry, [...path, key]),
    );
  }

  return [];
}
