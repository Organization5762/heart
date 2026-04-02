import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { Stream } from "@/components/stream";
import { DEFAULT_SCENE_CONFIGURATION } from "@/features/stream-console/scene-config";

const streamedImageState = vi.hoisted(() => ({
  fps: 24,
  frameBlob: new Blob(["frame"]),
  imgURL: "blob:frame-texture",
  isActive: true,
}));

const websocketState = vi.hoisted(() => ({
  socket: {
    url: "ws://localhost:8765/stream",
  },
}));

const streamCubeState = vi.hoisted(() => ({
  lastSceneConfig: null as typeof DEFAULT_SCENE_CONFIGURATION | null,
}));

vi.mock("@/actions/ws/providers/ImageProvider", () => ({
  useStreamedImage: () => streamedImageState,
}));

vi.mock("@/actions/ws/providers/PeripheralProvider", () => ({
  useConnectedPeripherals: () => ({}),
}));

vi.mock("@/actions/ws/providers/PeripheralEventsProvider", () => ({
  usePeripheralEvents: () => [],
}));

vi.mock("@/actions/ws/websocket", () => ({
  useWS: () => websocketState,
}));

vi.mock("@/components/stream-cube", () => ({
  StreamCube: ({
    frameBlob,
    onContextError,
    sceneConfig,
  }: {
    frameBlob: Blob | null;
    onContextError?: () => void;
    sceneConfig: typeof DEFAULT_SCENE_CONFIGURATION;
  }) => (
    <button
      type="button"
      onClick={() => onContextError?.()}
      ref={() => {
        expect(frameBlob).toBe(streamedImageState.frameBlob);
        streamCubeState.lastSceneConfig = sceneConfig;
      }}
    >
      trip-webgl
    </button>
  ),
}));

describe("Stream", () => {
  beforeEach(() => {
    streamedImageState.fps = 24;
    streamedImageState.frameBlob = new Blob(["frame"]);
    streamedImageState.imgURL = "blob:frame-texture";
    streamedImageState.isActive = true;
    websocketState.socket.url = "ws://localhost:8765/stream";
    streamCubeState.lastSceneConfig = null;
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

    expect(
      screen.getByRole("textbox", { name: "Sensor terminal command" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/fps:/i)).toHaveTextContent("fps: 24");
    expect(
      screen.getAllByText("ws://localhost:8765/stream").length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("Active").length).toBeGreaterThan(0);
  });

  it("starts the current stream cube with yaw-only rotation and a small wobble", () => {
    render(<Stream />);

    expect(streamCubeState.lastSceneConfig).toMatchObject({
      motion: {
        autoRotate: true,
        rotationX: 0,
        rotationY: DEFAULT_SCENE_CONFIGURATION.motion.rotationY,
        wobbleAmount: DEFAULT_SCENE_CONFIGURATION.motion.wobbleAmount,
      },
    });
    expect(streamCubeState.lastSceneConfig?.motion.wobbleAmount).toBeLessThan(
      0.05,
    );
  });
});
