import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PeripheralSensorDeck } from "@/components/peripheral-sensor-deck";

const simulationState = vi.hoisted(() => {
  const selectedSensor = {
    id: "dpad / payload.x",
    peripheralId: "dpad",
    label: "dpad / payload.x",
    path: "payload.x",
    value: 1,
    rawValue: 1,
    displayValue: "1.000",
    updatedAt: 0,
    tags: [],
    source: "live" as const,
    effectiveValue: 1,
    referenceValue: null,
    evaluationError: null,
  };

  return {
    clockSeconds: 3.5,
    history: {},
    overrides: {
      [selectedSensor.id]: {
        mode: "live" as const,
        constantValue: 0,
        expression: "0.4 + 0.2 * sin(t * 1.25)",
      },
    },
    resolvedSensors: [selectedSensor],
    selectedSensor,
    selectedSensorHistory: [],
    selectedSensorId: selectedSensor.id,
    setSelectedSensorId: vi.fn(),
    updateSensorOverride: vi.fn(),
    resetSensorOverride: vi.fn(),
    clearSelectedSensorHistory: vi.fn(),
  };
});

const useSensorSimulationMock = vi.hoisted(() => vi.fn(() => simulationState));

vi.mock("@/actions/ws/providers/PeripheralEventsProvider", () => ({
  usePeripheralEvents: () => [],
}));

vi.mock("@/features/stream-console/use-sensor-simulation", () => ({
  useSensorSimulation: useSensorSimulationMock,
}));

describe("PeripheralSensorDeck", () => {
  it("renders the selected sensor terminal when a slash-delimited sensor id is active", () => {
    render(<PeripheralSensorDeck />);

    expect(
      screen.getByRole("textbox", { name: "Sensor terminal command" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("dpad / payload.x").length).toBeGreaterThan(0);
  });

  it("passes a preferred sensor key into the simulation hook", () => {
    render(<PeripheralSensorDeck preferredSensorKey="dpad:payload.x" />);

    expect(useSensorSimulationMock).toHaveBeenLastCalledWith("dpad:payload.x");
  });
});
