import { render, screen } from "@testing-library/react";
import { act } from "react";

import { WSProvider, useWS } from "@/actions/ws/websocket";
import * as protocol from "@/actions/ws/protocol";

class FakeWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances: FakeWebSocket[] = [];

  url: string;
  binaryType = "blob";
  readyState = FakeWebSocket.CONNECTING;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  sent: string[] = [];

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  close() {
    this.readyState = FakeWebSocket.CLOSED;
  }

  send(message: string) {
    this.sent.push(message);
  }

  triggerOpen() {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.();
  }

  triggerClose() {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.();
  }

  triggerMessage(data: ArrayBuffer | Blob) {
    this.onmessage?.({ data } as MessageEvent);
  }
}

function ReadyStateProbe() {
  const { readyState } = useWS();
  return <div data-testid="ready-state">{readyState}</div>;
}

function SensorControlProbe() {
  const { sendSensorControl } = useWS();

  return (
    <button
      type="button"
      onClick={() => sendSensorControl("accelerometer:debug:z", 12.5)}
    >
      Send Sensor Control
    </button>
  );
}

describe("WSProvider", () => {
  beforeEach(() => {
    FakeWebSocket.instances = [];
    vi.useFakeTimers();
    vi.stubGlobal("WebSocket", FakeWebSocket);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  test("reconnects once after a disconnect and ignores stale socket callbacks", () => {
    render(
      <WSProvider
        url="ws://localhost:8765"
        retryDelay={100}
        maxRetryDelay={200}
      >
        <ReadyStateProbe />
      </WSProvider>,
    );

    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(screen.getByTestId("ready-state")).toHaveTextContent("0");

    act(() => {
      FakeWebSocket.instances[0].triggerOpen();
    });
    expect(screen.getByTestId("ready-state")).toHaveTextContent("1");

    act(() => {
      FakeWebSocket.instances[0].triggerClose();
    });
    expect(screen.getByTestId("ready-state")).toHaveTextContent("3");

    act(() => {
      vi.advanceTimersByTime(100);
    });
    expect(FakeWebSocket.instances).toHaveLength(2);

    act(() => {
      FakeWebSocket.instances[0].triggerClose();
      vi.advanceTimersByTime(200);
    });
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  test("stays disconnected when no websocket url is configured", () => {
    render(
      <WSProvider url={null} retryDelay={100} maxRetryDelay={200}>
        <ReadyStateProbe />
      </WSProvider>,
    );

    expect(FakeWebSocket.instances).toHaveLength(0);
    expect(screen.getByTestId("ready-state")).toHaveTextContent("3");
  });

  test("sends sensor control envelopes over the websocket", () => {
    render(
      <WSProvider
        url="ws://localhost:8765"
        retryDelay={100}
        maxRetryDelay={200}
      >
        <SensorControlProbe />
      </WSProvider>,
    );

    act(() => {
      FakeWebSocket.instances[0].triggerOpen();
    });

    act(() => {
      screen.getByRole("button", { name: "Send Sensor Control" }).click();
    });

    expect(FakeWebSocket.instances[0].sent).toEqual([
      JSON.stringify({
        kind: "control",
        command: "sensor_update",
        sensor_key: "accelerometer:debug:z",
        sensor_value: 12.5,
        clear: false,
      }),
    ]);
  });

  test("decodes blob websocket messages so binary frames render in Electron", async () => {
    const decodeSpy = vi
      .spyOn(protocol, "decodeStreamEvent")
      .mockReturnValue(null);

    render(
      <WSProvider
        url="ws://localhost:8765"
        retryDelay={100}
        maxRetryDelay={200}
      >
        <ReadyStateProbe />
      </WSProvider>,
    );

    act(() => {
      FakeWebSocket.instances[0].triggerOpen();
    });

    const payload = new Uint8Array([1, 2, 3]).buffer;
    FakeWebSocket.instances[0].triggerMessage(new Blob([payload]));
    await vi.waitFor(() => {
      expect(decodeSpy).toHaveBeenCalledTimes(1);
    });
    expect(decodeSpy.mock.calls[0]?.[0]).toBeInstanceOf(ArrayBuffer);
  });
});
