import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EventList } from "@/actions/peripherals/event_list";

type MockPeripheralEvent = {
  ts: number;
  msg: {
    type: "peripheral";
    payload: {
      peripheralInfo: {
        id: string | null;
        tags: Array<{
          name: string;
          variant: string;
          metadata?: Record<string, string>;
        }>;
      };
      data: unknown;
      payloadEncoding: number | null;
    };
  };
};

const peripheralEventsState = vi.hoisted(() => ({
  events: [] as MockPeripheralEvent[],
}));

vi.mock("@/actions/ws/providers/PeripheralEventsProvider", () => ({
  usePeripheralEvents: () => peripheralEventsState.events,
}));

describe("EventList", () => {
  it("freezes the rendered event rows while the operator pauses the log", async () => {
    const user = userEvent.setup();
    peripheralEventsState.events = [
      createPeripheralEvent({
        id: "alpha",
        variant: "dial",
        ts: 1_000,
      }),
    ];

    const { rerender } = render(<EventList />);

    expect(screen.getByText("1 Visible / 1 Cached")).toBeInTheDocument();
    expect(screen.getByText(/"id": "alpha"/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Pause" }));

    peripheralEventsState.events = [
      createPeripheralEvent({
        id: "beta",
        variant: "gyro",
        ts: 2_000,
      }),
      ...peripheralEventsState.events,
    ];
    rerender(<EventList />);

    expect(screen.getByRole("button", { name: "Resume" })).toBeInTheDocument();
    expect(screen.getByText("1 Visible / 1 Cached")).toBeInTheDocument();
    expect(screen.queryByText(/"id": "beta"/)).not.toBeInTheDocument();
    expect(screen.getByText(/"id": "alpha"/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Resume" }));

    expect(screen.getByText("2 Visible / 2 Cached")).toBeInTheDocument();
    expect(screen.getByText(/"id": "beta"/)).toBeInTheDocument();
  });

  it("filters rows by nested payload keys such as variant values", async () => {
    const user = userEvent.setup();
    peripheralEventsState.events = [
      createPeripheralEvent({
        id: "alpha",
        variant: "dial",
        ts: 1_000,
      }),
      createPeripheralEvent({
        id: "beta",
        variant: "gyro",
        ts: 2_000,
      }),
    ];

    render(<EventList />);

    await user.type(
      screen.getByRole("textbox", { name: "Event filter key" }),
      "variant",
    );
    await user.type(
      screen.getByRole("textbox", { name: "Event filter value" }),
      "gyro",
    );

    expect(screen.getByText("1 Visible / 2 Cached")).toBeInTheDocument();
    expect(screen.getByText(/"id": "beta"/)).toBeInTheDocument();
    expect(screen.queryByText(/"id": "alpha"/)).not.toBeInTheDocument();
  });
});

function createPeripheralEvent({
  id,
  variant,
  ts,
}: {
  id: string;
  variant: string;
  ts: number;
}): MockPeripheralEvent {
  return {
    ts,
    msg: {
      type: "peripheral",
      payload: {
        peripheralInfo: {
          id,
          tags: [
            {
              name: "input_variant",
              variant,
            },
          ],
        },
        data: {
          id,
          variant,
        },
        payloadEncoding: 1,
      },
    },
  };
}
