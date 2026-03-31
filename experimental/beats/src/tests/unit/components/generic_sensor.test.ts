import { collectPreviewMetrics } from "@/components/ui/peripherals/generic_sensor";
import { describe, expect, it } from "vitest";

describe("collectPreviewMetrics", () => {
  it("collects numeric and boolean leaves from nested payloads", () => {
    expect(
      collectPreviewMetrics({
        battery: {
          charging: true,
          voltage: 3.71,
        },
        imu: {
          x: 0.14,
          y: -0.22,
        },
      }),
    ).toEqual([
      {
        id: "battery.charging",
        kind: "boolean",
        label: "battery.charging",
        value: true,
      },
      {
        id: "battery.voltage",
        kind: "numeric",
        label: "battery.voltage",
        value: 3.71,
      },
      {
        id: "imu.x",
        kind: "numeric",
        label: "imu.x",
        value: 0.14,
      },
      {
        id: "imu.y",
        kind: "numeric",
        label: "imu.y",
        value: -0.22,
      },
    ]);
  });

  it("caps preview metrics to the first six leaves", () => {
    expect(
      collectPreviewMetrics({
        a: 1,
        b: 2,
        c: 3,
        d: 4,
        e: 5,
        f: 6,
        g: 7,
      }),
    ).toHaveLength(6);
  });
});
