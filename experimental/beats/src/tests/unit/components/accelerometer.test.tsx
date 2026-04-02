import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AccelerometerView } from "@/components/ui/peripherals/accelerometer";

const useSpecificPeripheralEventsMock = vi.hoisted(() => vi.fn());

vi.mock("@/actions/ws/providers/PeripheralEventsProvider", () => ({
  useSpecificPeripheralEvents: useSpecificPeripheralEventsMock,
}));

describe("AccelerometerView", () => {
  it("renders decoded axis values from direct peripheral payload data", () => {
    useSpecificPeripheralEventsMock.mockReturnValue([
      {
        msg: {
          payload: {
            data: {
              x: 1.25,
              y: -0.5,
              z: 9.81,
            },
          },
        },
      },
    ]);

    render(
      <AccelerometerView
        peripheral={{
          id: "accelerometer.debug",
          tags: [],
        }}
      />,
    );

    expect(screen.getAllByText("1.25").length).toBeGreaterThan(0);
    expect(screen.getAllByText("-0.50").length).toBeGreaterThan(0);
    expect(screen.getAllByText("9.81").length).toBeGreaterThan(0);
  });
});
