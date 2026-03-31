import { describe, expect, it } from "vitest";

import {
  formatPeripheralRecency,
  selectStableRecentPeripheralActivity,
  summarizeRecentPeripheralActivity,
} from "@/routes/index";

describe("home recent peripheral activity", () => {
  it("ranks recent devices by last activity and includes burst counts", () => {
    const now = 120_000;

    const summary = summarizeRecentPeripheralActivity(
      [
        {
          ts: now - 40_000,
          info: { id: "gamma", tags: [] },
          last_data: {},
        },
        {
          ts: now - 5_000,
          info: { id: "alpha", tags: [] },
          last_data: {},
        },
      ],
      [
        {
          ts: now - 3_000,
          msg: {
            type: "peripheral",
            payload: {
              peripheralInfo: { id: "alpha", tags: [] },
              data: {},
            },
          },
        },
        {
          ts: now - 12_000,
          msg: {
            type: "peripheral",
            payload: {
              peripheralInfo: { id: "beta", tags: [] },
              data: {},
            },
          },
        },
        {
          ts: now - 10_000,
          msg: {
            type: "peripheral",
            payload: {
              peripheralInfo: { id: "beta", tags: [] },
              data: {},
            },
          },
        },
      ],
      now,
    );

    expect(summary).toEqual([
      { id: "alpha", lastSeenTs: now - 3_000, eventCount: 1 },
      { id: "beta", lastSeenTs: now - 10_000, eventCount: 2 },
      { id: "gamma", lastSeenTs: now - 40_000, eventCount: 0 },
    ]);
  });

  it("filters devices that have gone stale", () => {
    const now = 90_000;

    const summary = summarizeRecentPeripheralActivity(
      [
        {
          ts: now - 61_000,
          info: { id: "stale", tags: [] },
          last_data: {},
        },
      ],
      [],
      now,
    );

    expect(summary).toEqual([]);
  });

  it("preserves visible ordering while appending newly active devices", () => {
    const activeDevices = [
      { id: "delta", lastSeenTs: 99_000, eventCount: 3 },
      { id: "alpha", lastSeenTs: 98_000, eventCount: 2 },
      { id: "gamma", lastSeenTs: 97_000, eventCount: 1 },
      { id: "beta", lastSeenTs: 96_000, eventCount: 1 },
    ];

    const summary = selectStableRecentPeripheralActivity(
      ["alpha", "beta", "gamma"],
      activeDevices,
      4,
    );

    expect(summary.map((device) => device.id)).toEqual([
      "alpha",
      "beta",
      "gamma",
      "delta",
    ]);
  });

  it("formats recency labels for fast-moving devices", () => {
    const now = 90_000;

    expect(formatPeripheralRecency(now - 2_000, now)).toBe("Just now");
    expect(formatPeripheralRecency(now - 15_000, now)).toBe("15s ago");
    expect(formatPeripheralRecency(now - 70_000, now)).toBe("1m ago");
  });
});
