import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { StreamNavigationPanel } from "@/components/stream-navigation-panel";

const sendNavigationControl = vi.fn();

vi.mock("@/actions/ws/providers/PeripheralEventsProvider", () => ({
  usePeripheralEvents: () => [],
}));

vi.mock("@/actions/ws/websocket", () => ({
  useWS: () => ({
    readyState: WebSocket.OPEN,
    sendNavigationControl,
  }),
}));

describe("StreamNavigationPanel", () => {
  it("sends browse and activate controls over the websocket", async () => {
    const user = userEvent.setup();

    render(<StreamNavigationPanel />);

    await user.click(screen.getByRole("button", { name: /next scene/i }));
    await user.click(screen.getByRole("button", { name: /active/i }));
    await user.click(
      screen.getByRole("button", { name: /alternative activate/i }),
    );

    expect(sendNavigationControl).toHaveBeenNthCalledWith(1, "browse", 1);
    expect(sendNavigationControl).toHaveBeenNthCalledWith(2, "activate");
    expect(sendNavigationControl).toHaveBeenNthCalledWith(
      3,
      "alternate_activate",
    );
  });
});
