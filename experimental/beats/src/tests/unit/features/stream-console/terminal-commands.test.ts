import {
  executeCommand,
  getCommandSuggestions,
  getSensorCommandKey,
} from "@/features/stream-console/terminal-commands";
import type {
  ResolvedSensorChannel,
  SensorOverride,
} from "@/features/stream-console/sensor-simulation";

const sensor: ResolvedSensorChannel = {
  id: "sensor.temperature",
  displayValue: "21.40",
  effectiveValue: 21.4,
  evaluationError: null,
  label: "Sensor Temperature",
  path: "value",
  peripheralId: "sensor.temperature",
  rawValue: 21.4,
  referenceValue: null,
  source: "live",
  tags: [],
  updatedAt: 0,
  value: 21.4,
};

const defaultOverride: SensorOverride = {
  constantValue: 0,
  expression: "0.4 + 0.2 * sin(t * 1.25)",
  mode: "live",
};

describe("terminal command utilities", () => {
  it("lists sensor-key suggestions for the select command", () => {
    const suggestions = getCommandSuggestions("select sensor", [sensor]);

    expect(suggestions).toEqual([
      {
        description: "Sensor Temperature (21.40)",
        value: `select ${getSensorCommandKey(sensor)}`,
      },
    ]);
  });

  it("pins the selected sensor to a constant via the set command", () => {
    const result = executeCommand("set 0.75", {
      overrides: {},
      selectedSensor: sensor,
      sensors: [sensor],
    });

    expect(result.actions).toEqual([
      {
        patch: {
          constantValue: 0.75,
          mode: "constant",
        },
        sensorId: sensor.id,
        type: "update-override",
      },
    ]);
    expect(result.messages[0]?.text).toContain("Pinned Sensor Temperature");
  });

  it("rejects invalid expressions before mutating overrides", () => {
    const result = executeCommand("expr missing_function(t)", {
      overrides: {
        [sensor.id]: defaultOverride,
      },
      selectedSensor: sensor,
      sensors: [sensor],
    });

    expect(result.actions).toEqual([]);
    expect(result.messages[0]?.level).toBe("error");
    expect(result.messages[0]?.text).toContain("missing_function");
  });

  it("describes the active override state with the show command", () => {
    const result = executeCommand("show", {
      overrides: {
        [sensor.id]: {
          ...defaultOverride,
          constantValue: 0.33,
          mode: "constant",
        },
      },
      selectedSensor: sensor,
      sensors: [sensor],
    });

    expect(result.messages[0]?.text).toContain("mode=constant");
    expect(result.messages[0]?.text).toContain("constant=0.330");
  });
});
