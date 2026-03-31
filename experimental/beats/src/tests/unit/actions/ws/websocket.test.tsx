import { render, screen } from "@testing-library/react";
import { act } from "react";

import { WSProvider, useWS } from "@/actions/ws/websocket";

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

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  close() {
    this.readyState = FakeWebSocket.CLOSED;
  }

  triggerOpen() {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.();
  }

  triggerClose() {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.();
  }
}

function ReadyStateProbe() {
  const { readyState } = useWS();
  return <div data-testid="ready-state">{readyState}</div>;
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
});
