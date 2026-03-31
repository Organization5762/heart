import {
  appendSensorHistory,
  compileSensorExpression,
  extractSensorChannels,
  resolveSensorChannel,
} from "@/features/stream-console/sensor-simulation";

describe("sensor simulation utilities", () => {
  it("extracts numeric and boolean channels from connected peripherals", () => {
    const channels = extractSensorChannels({
      accel: {
        ts: 100,
        info: {
          id: "accel",
          tags: [
            {
              name: "input_variant",
              variant: "accelerometer",
            },
          ],
        },
        last_data: {
          x: 0.25,
          y: -0.5,
          ready: true,
        },
      },
    });

    expect(channels.map((channel) => channel.label)).toEqual([
      "accel / ready",
      "accel / x",
      "accel / y",
    ]);
    expect(channels[0]?.value).toBe(1);
    expect(channels[1]?.value).toBe(0.25);
    expect(channels[2]?.value).toBe(-0.5);
  });

  it("falls back to demo channels when no live numeric sensors are available", () => {
    const channels = extractSensorChannels({});

    expect(channels).toHaveLength(2);
    expect(channels.every((channel) => channel.source === "demo")).toBe(true);
  });

  it("compiles helper-based functions that depend on time", () => {
    const compiled = compileSensorExpression("mix(10, 20, triangle(t, 8))");

    expect(compiled.error).toBeNull();
    expect(compiled.evaluate?.(2)).toBeCloseTo(15);
  });

  it("falls back to live sensor values when function evaluation fails", () => {
    const resolved = resolveSensorChannel(
      {
        id: "demo.motion",
        label: "Demo Motion",
        path: "value",
        peripheralId: "demo.motion",
        value: 0.5,
        rawValue: 0.5,
        displayValue: "0.50",
        updatedAt: 0,
        tags: [],
        source: "demo",
      },
      {
        mode: "function",
        constantValue: 0,
        expression: "missing_function(t)",
      },
      4,
    );

    expect(resolved.effectiveValue).toBe(0.5);
    expect(resolved.referenceValue).toBeNull();
    expect(resolved.evaluationError).toContain("missing_function");
  });

  it("caps stored sensor history to the requested limit", () => {
    const history = appendSensorHistory(
      [
        {
          timeSeconds: 1,
          liveValue: 1,
          effectiveValue: 1,
          referenceValue: null,
        },
        {
          timeSeconds: 2,
          liveValue: 2,
          effectiveValue: 2,
          referenceValue: null,
        },
      ],
      {
        timeSeconds: 3,
        liveValue: 3,
        effectiveValue: 3,
        referenceValue: null,
      },
      2,
    );

    expect(history).toEqual([
      {
        timeSeconds: 2,
        liveValue: 2,
        effectiveValue: 2,
        referenceValue: null,
      },
      {
        timeSeconds: 3,
        liveValue: 3,
        effectiveValue: 3,
        referenceValue: null,
      },
    ]);
  });
});
