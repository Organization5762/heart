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
});
