import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Stream } from "@/components/stream";

const streamedImageState = vi.hoisted(() => ({
  fps: 24,
  imgURL: "blob:frame-texture",
  isActive: true,
}));

const websocketState = vi.hoisted(() => ({
  socket: {
    url: "ws://localhost:8765/stream",
  },
}));

vi.mock("@/actions/ws/providers/ImageProvider", () => ({
  useStreamedImage: () => streamedImageState,
}));

vi.mock("@/actions/ws/providers/PeripheralProvider", () => ({
  useConnectedPeripherals: () => ({}),
}));

vi.mock("@/actions/ws/websocket", () => ({
  useWS: () => websocketState,
}));

vi.mock("@/components/stream-cube", () => ({
  StreamCube: ({ onContextError }: { onContextError?: () => void }) => (
    <button type="button" onClick={() => onContextError?.()}>
      trip-webgl
    </button>
  ),
}));

describe("Stream", () => {
  beforeEach(() => {
    streamedImageState.fps = 24;
    streamedImageState.imgURL = "blob:frame-texture";
    streamedImageState.isActive = true;
    websocketState.socket.url = "ws://localhost:8765/stream";
  });

  it("falls back to the image viewer when the WebGL scene reports a context error", async () => {
    const user = userEvent.setup();

    render(<Stream />);

    await user.click(screen.getByRole("button", { name: "trip-webgl" }));

    expect(screen.getByRole("img", { name: "stream" })).toHaveAttribute(
      "src",
      streamedImageState.imgURL,
    );
  });

  it("shows live telemetry from the websocket stream in the footer", () => {
    render(<Stream />);

    expect(screen.getByText(/fps:/i)).toHaveTextContent("fps: 24");
    expect(
      screen.getAllByText("ws://localhost:8765/stream").length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("Active").length).toBeGreaterThan(0);
  });
});
