import { fireEvent, render, screen } from "@testing-library/react";
import { act } from "react";

import { useSensorSimulation } from "@/features/stream-console/use-sensor-simulation";

const peripheralState = {
  "sensor.1": {
    ts: 100,
    info: {
      id: "sensor.1",
      tags: [],
    },
    last_data: {
      payload: {
        level: 0.25,
      },
    },
  },
};

const websocketState = {
  connected: true,
  sendSensorControl: vi.fn((...args: [string, number | null]) => {
    void args;
    return websocketState.connected;
  }),
};

vi.mock("@/actions/ws/providers/PeripheralProvider", () => ({
  useConnectedPeripherals: () => peripheralState,
}));

vi.mock("@/actions/ws/websocket", () => ({
  useWS: () => ({
    sendSensorControl: websocketState.sendSensorControl,
  }),
}));

function SensorSimulationProbe() {
  const simulation = useSensorSimulation("sensor.1:payload.level");

  return (
    <div>
      <div data-testid="selected-sensor">
        {simulation.selectedSensor?.commandKey ?? "none"}
      </div>
      <button
        type="button"
        onClick={() => {
          if (!simulation.selectedSensor) {
            return;
          }
          simulation.updateSensorOverride(simulation.selectedSensor.id, {
            mode: "constant",
            constantValue: 1,
          });
        }}
      >
        Engage
      </button>
      <button
        type="button"
        onClick={() => {
          if (!simulation.selectedSensor) {
            return;
          }
          simulation.resetSensorOverride(simulation.selectedSensor.id);
        }}
      >
        Release
      </button>
    </div>
  );
}

describe("useSensorSimulation", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    websocketState.connected = true;
    websocketState.sendSensorControl.mockClear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("retries dropped clear commands after the websocket reconnects", () => {
    render(<SensorSimulationProbe />);

    expect(screen.getByTestId("selected-sensor")).toHaveTextContent(
      "sensor.1:payload.level",
    );

    fireEvent.click(screen.getByRole("button", { name: "Engage" }));

    act(() => {
      vi.advanceTimersByTime(250);
    });

    expect(websocketState.sendSensorControl).toHaveBeenCalledWith(
      "sensor.1:payload.level",
      1,
    );

    websocketState.connected = false;
    fireEvent.click(screen.getByRole("button", { name: "Release" }));

    act(() => {
      vi.advanceTimersByTime(250);
    });

    const clearsWhileDisconnected =
      websocketState.sendSensorControl.mock.calls.filter(
        ([, value]) => value === null,
      );
    expect(clearsWhileDisconnected).toHaveLength(1);

    websocketState.connected = true;

    act(() => {
      vi.advanceTimersByTime(250);
    });

    const clearsAfterReconnect =
      websocketState.sendSensorControl.mock.calls.filter(
        ([, value]) => value === null,
      );
    expect(clearsAfterReconnect).toHaveLength(2);

    act(() => {
      vi.advanceTimersByTime(250);
    });

    const clearsAfterSuccess =
      websocketState.sendSensorControl.mock.calls.filter(
        ([, value]) => value === null,
      );
    expect(clearsAfterSuccess).toHaveLength(2);
  });
});
