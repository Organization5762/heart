import { describe, expect, it } from "vitest";

import {
  summarizeNavigationTelemetry,
  type NavigationIntentSnapshot,
} from "@/features/stream-console/navigation-telemetry";

type TestEvent = {
  ts: number;
  msg: {
    payload: {
      peripheralInfo: {
        id: string;
        tags: Array<{ name: string; variant: string }>;
      };
      data: unknown;
    };
  };
};

function navigationEvent(
  ts: number,
  data: Record<string, unknown>,
  sourceId = "navigation",
): TestEvent {
  return {
    ts,
    msg: {
      payload: {
        peripheralInfo: {
          id: sourceId,
          tags: [
            {
              name: "input_debug_stream",
              variant: "navigation.intent",
            },
          ],
        },
        data,
      },
    },
  };
}

describe("summarizeNavigationTelemetry", () => {
  it("tracks pending browse offset until an activate commits it", () => {
    const summary = summarizeNavigationTelemetry([
      navigationEvent(3000, { source: "keyboard.down" }),
      navigationEvent(2000, { source: "keyboard.right", step: 1 }),
      navigationEvent(1000, { source: "keyboard.right", step: 1 }),
    ] as Parameters<typeof summarizeNavigationTelemetry>[0]);

    expect(summary.pendingBrowseOffset).toBe(0);
    expect(summary.lastCommittedDelta).toBe(2);
    expect(summary.browseCount).toBe(2);
    expect(summary.activateCount).toBe(1);
    expect(summary.inferredModeState).toBe("committed");
  });

  it("resets pending browse state when alternate activate returns to select mode", () => {
    const summary = summarizeNavigationTelemetry([
      navigationEvent(3000, { source: "keyboard.up" }),
      navigationEvent(2000, { source: "keyboard.left", step: -1 }),
    ] as Parameters<typeof summarizeNavigationTelemetry>[0]);

    expect(summary.pendingBrowseOffset).toBe(0);
    expect(summary.lastCommittedDelta).toBe(0);
    expect(summary.alternateCount).toBe(1);
    expect(summary.inferredModeState).toBe("select_mode");
  });

  it("ignores non-navigation payloads and keeps the newest intents first", () => {
    const summary = summarizeNavigationTelemetry([
      {
        ts: 4000,
        msg: {
          payload: {
            peripheralInfo: {
              id: "keyboard",
              tags: [{ name: "input_debug_stream", variant: "keyboard.tick" }],
            },
            data: { source: "keyboard.left", step: -1 },
          },
        },
      },
      navigationEvent(3000, { source: "gamepad.south" }),
      navigationEvent(2000, { source: "switch.rotary", step: 2 }),
    ] as Parameters<typeof summarizeNavigationTelemetry>[0]);

    expect(summary.recentIntents.map((intent) => intent.kind)).toEqual([
      "activate",
      "browse",
    ]);
    expect(
      (summary.lastIntent as NavigationIntentSnapshot | null)?.source,
    ).toBe("gamepad.south");
  });
});
