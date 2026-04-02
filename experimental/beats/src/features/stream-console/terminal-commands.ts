import {
  SENSOR_FUNCTION_PRESETS,
  compileSensorExpression,
  formatSensorValue,
  type ResolvedSensorChannel,
  type SensorOverride,
} from "./sensor-simulation";

const COMMANDS = [
  {
    name: "help",
    description: "Show the available sensor-control commands.",
  },
  {
    name: "sensors",
    description: "List addressable sensors and their current values.",
  },
  {
    name: "show",
    description: "Print the active sensor status.",
  },
  {
    name: "select",
    description: "Choose the active sensor by command key.",
  },
  {
    name: "live",
    description: "Follow the live hardware value for the active sensor.",
  },
  {
    name: "set",
    description: "Pin the active sensor to a constant numeric value.",
  },
  {
    name: "expr",
    description: "Drive the active sensor with an expression of t.",
  },
  {
    name: "preset",
    description: "Apply a named function preset to the active sensor.",
  },
  {
    name: "clear",
    description: "Remove the active sensor override.",
  },
  {
    name: "history",
    description: "Clear the current sensor history buffer.",
  },
] as const;

export type CommandSuggestion = {
  value: string;
  description: string;
};

export type SensorTerminalMessage = {
  level: "info" | "error" | "system";
  text: string;
};

export type SensorTerminalAction =
  | { type: "select-sensor"; sensorId: string }
  | {
      type: "update-override";
      sensorId: string;
      patch: Partial<SensorOverride>;
    }
  | { type: "reset-override"; sensorId: string }
  | { type: "clear-history" };

export type ExecuteCommandResult = {
  actions: SensorTerminalAction[];
  messages: SensorTerminalMessage[];
};

type CommandContext = {
  overrides: Record<string, SensorOverride>;
  selectedSensor: ResolvedSensorChannel | null;
  sensors: ResolvedSensorChannel[];
};

type SensorMatch =
  | {
      kind: "match";
      sensor: ResolvedSensorChannel;
    }
  | {
      kind: "error";
      message: string;
    };

export function getSensorCommandKey(
  sensor: Pick<ResolvedSensorChannel, "path" | "peripheralId">,
) {
  return `${sensor.peripheralId}:${sensor.path}`;
}

export function getCommandSuggestions(
  input: string,
  sensors: ResolvedSensorChannel[],
) {
  const tokens = tokenizeCommandInput(input);
  const endsWithSpace = /\s$/.test(input);

  if (tokens.length === 0) {
    return COMMANDS.slice(0, 6).map((command) => ({
      value:
        command.name === "select" ||
        command.name === "set" ||
        command.name === "expr" ||
        command.name === "preset" ||
        command.name === "history"
          ? `${command.name} `
          : command.name,
      description: command.description,
    }));
  }

  if (tokens.length === 1 && !endsWithSpace) {
    const prefix = tokens[0]?.toLowerCase() ?? "";
    return COMMANDS.filter((command) => command.name.startsWith(prefix)).map(
      (command) => ({
        value:
          command.name === "select" ||
          command.name === "set" ||
          command.name === "expr" ||
          command.name === "preset" ||
          command.name === "history"
            ? `${command.name} `
            : command.name,
        description: command.description,
      }),
    );
  }

  const command = tokens[0]?.toLowerCase() ?? "";
  const argumentPrefix = endsWithSpace
    ? ""
    : (tokens.at(-1)?.toLowerCase() ?? "");

  if (command === "select") {
    return sensors
      .map((sensor) => ({
        value: `select ${getSensorCommandKey(sensor)}`,
        description: `${sensor.label} (${formatSensorValue(sensor.effectiveValue, 2)})`,
      }))
      .filter((suggestion) =>
        suggestion.value.toLowerCase().includes(argumentPrefix),
      )
      .slice(0, 8);
  }

  if (command === "preset") {
    return SENSOR_FUNCTION_PRESETS.map((preset) => ({
      value: `preset ${preset.label.toLowerCase()}`,
      description: preset.expression,
    })).filter((suggestion) =>
      suggestion.value.toLowerCase().startsWith(`preset ${argumentPrefix}`),
    );
  }

  if (command === "history") {
    return [
      {
        value: "history clear",
        description: "Clear the selected sensor trace buffer.",
      },
    ].filter((suggestion) =>
      suggestion.value.toLowerCase().startsWith(`history ${argumentPrefix}`),
    );
  }

  return [];
}

export function executeCommand(input: string, context: CommandContext) {
  const trimmedInput = input.trim();
  if (!trimmedInput) {
    return errorResult("Enter a command or type `help`.");
  }

  const tokens = tokenizeCommandInput(trimmedInput);
  const command = tokens[0]?.toLowerCase() ?? "";

  switch (command) {
    case "help":
      return {
        actions: [],
        messages: COMMANDS.map((item) => ({
          level: "system" as const,
          text: `${item.name.padEnd(7)} ${item.description}`,
        })),
      };
    case "sensors":
      return {
        actions: [],
        messages: context.sensors.map((sensor) => ({
          level: "info" as const,
          text: `${getSensorCommandKey(sensor)}  ${sensor.label}  live=${formatSensorValue(sensor.value, 2)} applied=${formatSensorValue(sensor.effectiveValue, 2)}`,
        })),
      };
    case "show":
      return describeSelectedSensor(context);
    case "select":
      return handleSelect(tokens[1], context.sensors);
    case "live":
      return handleLive(context);
    case "set":
      return handleSet(tokens[1], context);
    case "expr":
      return handleExpression(trimmedInput, context);
    case "preset":
      return handlePreset(tokens[1], context);
    case "clear":
      return handleClear(context);
    case "history":
      return handleHistory(tokens[1], context);
    default:
      return errorResult(`Unknown command: ${command}. Type \`help\`.`);
  }
}

function handleSelect(
  sensorToken: string | undefined,
  sensors: ResolvedSensorChannel[],
): ExecuteCommandResult {
  if (!sensorToken) {
    return errorResult("Usage: select <sensor-key>");
  }

  const match = findSensor(sensorToken, sensors);
  if (match.kind === "error") {
    return errorResult(match.message);
  }

  return {
    actions: [{ type: "select-sensor", sensorId: match.sensor.id }],
    messages: [
      {
        level: "info",
        text: `Selected ${match.sensor.label} (${getSensorCommandKey(match.sensor)}).`,
      },
    ],
  };
}

function handleLive(context: CommandContext): ExecuteCommandResult {
  if (!context.selectedSensor) {
    return errorResult("Select a sensor first with `select <sensor-key>`.");
  }

  return {
    actions: [
      {
        type: "update-override",
        sensorId: context.selectedSensor.id,
        patch: { mode: "live" },
      },
    ],
    messages: [
      {
        level: "info",
        text: `Following live input for ${context.selectedSensor.label}.`,
      },
    ],
  };
}

function handleSet(
  rawValue: string | undefined,
  context: CommandContext,
): ExecuteCommandResult {
  if (!context.selectedSensor) {
    return errorResult("Select a sensor first with `select <sensor-key>`.");
  }

  if (!rawValue) {
    return errorResult("Usage: set <number>");
  }

  const parsedValue = Number(rawValue);
  if (!Number.isFinite(parsedValue)) {
    return errorResult(`Expected a finite number, received "${rawValue}".`);
  }

  return {
    actions: [
      {
        type: "update-override",
        sensorId: context.selectedSensor.id,
        patch: {
          constantValue: parsedValue,
          mode: "constant",
        },
      },
    ],
    messages: [
      {
        level: "info",
        text: `Pinned ${context.selectedSensor.label} to ${formatSensorValue(parsedValue, 3)}.`,
      },
    ],
  };
}

function handleExpression(
  input: string,
  context: CommandContext,
): ExecuteCommandResult {
  if (!context.selectedSensor) {
    return errorResult("Select a sensor first with `select <sensor-key>`.");
  }

  const expression = input.replace(/^expr\s+/i, "").trim();
  if (!expression) {
    return errorResult("Usage: expr <expression>");
  }

  const compiled = compileSensorExpression(expression);
  if (compiled.error) {
    return errorResult(compiled.error);
  }

  try {
    compiled.evaluate?.(0);
  } catch (error) {
    return errorResult(
      error instanceof Error ? error.message : "Unable to evaluate expression.",
    );
  }

  return {
    actions: [
      {
        type: "update-override",
        sensorId: context.selectedSensor.id,
        patch: {
          expression,
          mode: "function",
        },
      },
    ],
    messages: [
      {
        level: "info",
        text: `Applied expression to ${context.selectedSensor.label}: ${expression}`,
      },
    ],
  };
}

function handlePreset(
  presetToken: string | undefined,
  context: CommandContext,
): ExecuteCommandResult {
  if (!context.selectedSensor) {
    return errorResult("Select a sensor first with `select <sensor-key>`.");
  }

  if (!presetToken) {
    return errorResult("Usage: preset <breath|pulse|sweep>");
  }

  const preset = SENSOR_FUNCTION_PRESETS.find(
    (item) => item.label.toLowerCase() === presetToken.toLowerCase(),
  );
  if (!preset) {
    return errorResult(`Unknown preset: ${presetToken}.`);
  }

  return {
    actions: [
      {
        type: "update-override",
        sensorId: context.selectedSensor.id,
        patch: {
          expression: preset.expression,
          mode: "function",
        },
      },
    ],
    messages: [
      {
        level: "info",
        text: `Loaded preset ${preset.label} for ${context.selectedSensor.label}.`,
      },
    ],
  };
}

function handleClear(context: CommandContext): ExecuteCommandResult {
  if (!context.selectedSensor) {
    return errorResult("Select a sensor first with `select <sensor-key>`.");
  }

  return {
    actions: [
      {
        type: "reset-override",
        sensorId: context.selectedSensor.id,
      },
    ],
    messages: [
      {
        level: "info",
        text: `Released external control for ${context.selectedSensor.label}.`,
      },
    ],
  };
}

function handleHistory(
  actionToken: string | undefined,
  context: CommandContext,
): ExecuteCommandResult {
  if (actionToken !== "clear") {
    return errorResult("Usage: history clear");
  }

  if (!context.selectedSensor) {
    return errorResult("Select a sensor first with `select <sensor-key>`.");
  }

  return {
    actions: [{ type: "clear-history" }],
    messages: [
      {
        level: "info",
        text: `Cleared the history trace for ${context.selectedSensor.label}.`,
      },
    ],
  };
}

function describeSelectedSensor(context: CommandContext): ExecuteCommandResult {
  if (!context.selectedSensor) {
    return errorResult("No sensor is currently selected.");
  }

  const override = context.overrides[context.selectedSensor.id];
  const mode = override?.mode ?? "live";
  const detail =
    mode === "constant"
      ? `constant=${formatSensorValue(override?.constantValue ?? 0, 3)}`
      : mode === "function"
        ? `expr=${override?.expression ?? ""}`
        : "following live input";

  return {
    actions: [],
    messages: [
      {
        level: "info",
        text: `${context.selectedSensor.label} (${getSensorCommandKey(context.selectedSensor)}) mode=${mode} live=${formatSensorValue(context.selectedSensor.value, 3)} applied=${formatSensorValue(context.selectedSensor.effectiveValue, 3)} ${detail}`,
      },
    ],
  };
}

function findSensor(
  token: string,
  sensors: ResolvedSensorChannel[],
): SensorMatch {
  const normalizedToken = token.toLowerCase();
  const exactMatch = sensors.find(
    (sensor) =>
      getSensorCommandKey(sensor).toLowerCase() === normalizedToken ||
      sensor.label.toLowerCase() === normalizedToken,
  );

  if (exactMatch) {
    return {
      kind: "match",
      sensor: exactMatch,
    };
  }

  const partialMatches = sensors.filter((sensor) =>
    getSensorCommandKey(sensor).toLowerCase().includes(normalizedToken),
  );

  if (partialMatches.length === 1) {
    return {
      kind: "match",
      sensor: partialMatches[0],
    };
  }

  if (partialMatches.length > 1) {
    return {
      kind: "error",
      message: `Sensor key is ambiguous: ${partialMatches
        .map((sensor) => getSensorCommandKey(sensor))
        .join(", ")}`,
    };
  }

  return {
    kind: "error",
    message: `Sensor not found: ${token}`,
  };
}

function tokenizeCommandInput(input: string) {
  return Array.from(input.matchAll(/"([^"]*)"|'([^']*)'|(\S+)/g), (match) => {
    return match[1] ?? match[2] ?? match[3] ?? "";
  });
}

function errorResult(message: string): ExecuteCommandResult {
  return {
    actions: [],
    messages: [{ level: "error", text: message }],
  };
}
