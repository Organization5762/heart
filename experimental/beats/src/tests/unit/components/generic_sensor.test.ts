import {
  collectPreviewMetrics,
  groupPreviewMetrics,
} from "@/components/ui/peripherals/generic_sensor";
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
        groupLabel: "Battery",
        kind: "boolean",
        label: "battery.charging",
        signalLabel: "charging",
        value: true,
      },
      {
        id: "battery.voltage",
        groupLabel: "Battery",
        kind: "numeric",
        label: "battery.voltage",
        signalLabel: "voltage",
        value: 3.71,
      },
      {
        id: "imu.x",
        groupLabel: "Imu",
        kind: "numeric",
        label: "imu.x",
        signalLabel: "x",
        value: 0.14,
      },
      {
        id: "imu.y",
        groupLabel: "Imu",
        kind: "numeric",
        label: "imu.y",
        signalLabel: "y",
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

describe("groupPreviewMetrics", () => {
  it("groups like sensor families such as dpad signals together", () => {
    const metrics = collectPreviewMetrics({
      dpad: {
        down: false,
        left: true,
        right: false,
        up: true,
      },
      trigger: {
        pressure: 0.42,
      },
    });

    expect(groupPreviewMetrics(metrics)).toEqual([
      {
        id: "dpad",
        label: "Dpad",
        metrics: [
          expect.objectContaining({
            id: "dpad.down",
            signalLabel: "down",
          }),
          expect.objectContaining({
            id: "dpad.left",
            signalLabel: "left",
          }),
          expect.objectContaining({
            id: "dpad.right",
            signalLabel: "right",
          }),
          expect.objectContaining({
            id: "dpad.up",
            signalLabel: "up",
          }),
        ],
      },
      {
        id: "trigger",
        label: "Trigger",
        metrics: [
          expect.objectContaining({
            id: "trigger.pressure",
            signalLabel: "pressure",
          }),
        ],
      },
    ]);
  });
});
