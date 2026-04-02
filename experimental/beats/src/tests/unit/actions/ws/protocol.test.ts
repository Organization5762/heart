import { afterEach, describe, expect, it, vi } from "vitest";

const FRAME_BYTES = new Uint8Array([1, 2, 3, 4]);

async function importProtocolWithDecodedEnvelope(decodedEnvelope: unknown) {
  vi.resetModules();
  vi.doMock("protobufjs", () => ({
    parse: () => ({
      root: {
        lookupType: () => ({
          decode: () => decodedEnvelope,
        }),
      },
    }),
  }));

  return import("@/actions/ws/protocol");
}

describe("decodeStreamEvent", () => {
  afterEach(() => {
    vi.resetModules();
    vi.doUnmock("protobufjs");
  });

  it("accepts camelCase frame payloads so streamed images survive decoder field normalization", async () => {
    const { decodeStreamEvent } = await importProtocolWithDecodedEnvelope({
      frame: {
        pngData: FRAME_BYTES,
      },
    });

    const decoded = decodeStreamEvent(new ArrayBuffer(0));

    expect(decoded).toEqual({
      type: "frame",
      payload: {
        pngData: FRAME_BYTES,
      },
    });
  });

  it("accepts snake_case frame payloads so the protobuf schema remains wire compatible", async () => {
    const { decodeStreamEvent } = await importProtocolWithDecodedEnvelope({
      frame: {
        png_data: FRAME_BYTES,
      },
    });

    const decoded = decodeStreamEvent(new ArrayBuffer(0));

    expect(decoded).toEqual({
      type: "frame",
      payload: {
        pngData: FRAME_BYTES,
      },
    });
  });

  it("defaults peripheral locations to the display origin so older payloads stay spatially valid", async () => {
    const { decodeStreamEvent } = await importProtocolWithDecodedEnvelope({
      peripheral: {
        peripheralInfo: {
          id: "sensor-1",
          tags: [],
        },
        payload: new TextEncoder().encode("{}"),
        payloadEncoding: 1,
      },
    });

    const decoded = decodeStreamEvent(new ArrayBuffer(0));

    expect(decoded).toEqual({
      type: "peripheral",
      payload: {
        peripheralInfo: {
          id: "sensor-1",
          tags: [],
          location: { x: 0, y: 0, z: 0, time: null },
        },
        data: {},
        payloadEncoding: 1,
      },
    });
  });

  it("preserves xyz and time when websocket peripheral metadata includes a 4d location", async () => {
    const { decodeStreamEvent } = await importProtocolWithDecodedEnvelope({
      peripheral: {
        peripheralInfo: {
          id: "sensor-2",
          tags: [],
          location: {
            x: 1.25,
            y: -2.5,
            z: 7.75,
            time: "2024-01-02T03:04:05+00:00",
          },
        },
        payload: new TextEncoder().encode("{}"),
        payloadEncoding: 1,
      },
    });

    const decoded = decodeStreamEvent(new ArrayBuffer(0));

    expect(decoded).toEqual({
      type: "peripheral",
      payload: {
        peripheralInfo: {
          id: "sensor-2",
          tags: [],
          location: {
            x: 1.25,
            y: -2.5,
            z: 7.75,
            time: "2024-01-02T03:04:05+00:00",
          },
        },
        data: {},
        payloadEncoding: 1,
      },
    });
  });
});
