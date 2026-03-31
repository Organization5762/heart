import { render, screen } from "@testing-library/react";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import {
  EVENT_BATCH_INTERVAL_MS,
  PeripheralEventsProvider,
  usePeripheralEvents,
} from "@/actions/ws/providers/PeripheralEventsProvider";
import { stream } from "@/actions/ws/websocket";

function EventProbe() {
  const events = usePeripheralEvents();
  return (
    <div data-testid="event-state">
      {JSON.stringify({
        count: events.length,
        latestId: events[0]?.msg.payload.peripheralInfo.id ?? null,
      })}
    </div>
  );
}

function emitPeripheralEvent(id: string) {
  stream.next({
    type: "peripheral",
    payload: {
      peripheralInfo: {
        id,
        tags: [],
      },
      data: { id },
      payloadEncoding: 1,
    },
  });
}

describe("PeripheralEventsProvider", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("batches fast event bursts before publishing them to consumers", () => {
    render(
      <PeripheralEventsProvider>
        <EventProbe />
      </PeripheralEventsProvider>,
    );

    act(() => {
      emitPeripheralEvent("first");
      emitPeripheralEvent("second");
    });

    expect(screen.getByTestId("event-state")).toHaveTextContent(
      JSON.stringify({ count: 0, latestId: null }),
    );

    act(() => {
      vi.advanceTimersByTime(EVENT_BATCH_INTERVAL_MS);
    });

    expect(screen.getByTestId("event-state")).toHaveTextContent(
      JSON.stringify({ count: 2, latestId: "second" }),
    );
  });
});
