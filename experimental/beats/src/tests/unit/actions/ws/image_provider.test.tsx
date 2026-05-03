import { render, screen } from "@testing-library/react";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import {
  ImageProvider,
  useStreamedImage,
} from "@/actions/ws/providers/ImageProvider";
import { stream } from "@/actions/ws/websocket";

function ImageProbe() {
  const { imgURL, fps, isActive } = useStreamedImage();

  return (
    <div data-testid="image-state">
      {JSON.stringify({ imgURL, fps, isActive })}
    </div>
  );
}

function emitFrame(value: number) {
  stream.next({
    type: "frame",
    payload: {
      pngData: new Uint8Array([value]),
    },
  });
}

describe("ImageProvider", () => {
  const createObjectURL = vi.fn();
  const revokeObjectURL = vi.fn();

  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal("URL", {
      createObjectURL,
      revokeObjectURL,
    });
    createObjectURL.mockReset();
    revokeObjectURL.mockReset();
    createObjectURL
      .mockReturnValueOnce("blob:first-frame")
      .mockReturnValueOnce("blob:second-frame");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  test("keeps the previous blob url alive briefly so async consumers can finish decoding", () => {
    render(
      <ImageProvider>
        <ImageProbe />
      </ImageProvider>,
    );

    act(() => {
      emitFrame(1);
      vi.advanceTimersByTime(16);
      emitFrame(2);
    });

    expect(screen.getByTestId("image-state")).toHaveTextContent(
      JSON.stringify({
        imgURL: "blob:second-frame",
        fps: 125,
        isActive: true,
      }),
    );
    expect(revokeObjectURL).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(999);
    });
    expect(revokeObjectURL).not.toHaveBeenCalled();

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:first-frame");
  });
});
