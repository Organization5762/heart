import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PeripheralTree } from "@/actions/peripherals/peripheral_tree";

type MockPeripheralSnapshot = {
  ts: number;
  info: {
    id: string | null;
    tags: Array<{
      name: string;
      variant: string;
      metadata?: Record<string, string>;
    }>;
  };
  last_data: unknown;
};

const connectedPeripheralState = vi.hoisted(() => ({
  peripherals: {} as Record<string, MockPeripheralSnapshot>,
}));

vi.mock("@/actions/ws/providers/PeripheralProvider", () => ({
  useConnectedPeripherals: () => connectedPeripheralState.peripherals,
}));

describe("PeripheralTree", () => {
  it("renders detected sensors under shared input-variant and mode branches", () => {
    connectedPeripheralState.peripherals = {
      "imu.1": createPeripheralSnapshot({
        id: "imu.1",
        variant: "accelerometer",
        mode: "stream",
        ts: 2_000,
      }),
      "imu.2": createPeripheralSnapshot({
        id: "imu.2",
        variant: "accelerometer",
        mode: "stream",
        ts: 1_000,
      }),
      "switch.1": createPeripheralSnapshot({
        id: "switch.1",
        variant: "button",
        mode: "event",
        ts: 3_000,
      }),
    };

    render(<PeripheralTree hierarchy={[["input_variant", "mode"]]} />);

    expect(
      screen.getByRole("heading", {
        level: 3,
        name: "input variant / accelerometer",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        level: 3,
        name: "mode / stream",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("imu.1")).toBeInTheDocument();
    expect(screen.getByText("imu.2")).toBeInTheDocument();
    expect(screen.getAllByText("input variant / accelerometer")).toHaveLength(
      1,
    );
    expect(screen.getByText("switch.1")).toBeInTheDocument();
  });
});

function createPeripheralSnapshot({
  id,
  mode,
  ts,
  variant,
}: {
  id: string;
  mode: string;
  ts: number;
  variant: string;
}): MockPeripheralSnapshot {
  return {
    ts,
    info: {
      id,
      tags: [
        {
          name: "input_variant",
          variant,
        },
        {
          name: "mode",
          variant: mode,
        },
      ],
    },
    last_data: {
      value: ts,
    },
  };
}
