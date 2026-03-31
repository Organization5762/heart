import { parse } from "protobufjs";

import protoSchema from "../../../../../src/heart/device/beats/proto/beats_streaming.proto?raw";

type PeripheralTag = {
  name: string;
  variant: string;
  metadata?: Record<string, string>;
};

type PeripheralInfo = {
  id?: string | null;
  tags: PeripheralTag[];
};

type PeripheralPayload = {
  peripheralInfo: PeripheralInfo;
  data: unknown;
  payloadEncoding: number | null;
};

type FramePayload = {
  pngData: Uint8Array;
};

export type StreamEvent =
  | { type: "frame"; payload: FramePayload }
  | { type: "peripheral"; payload: PeripheralPayload };

const root = parse(protoSchema, { keepCase: true }).root;
const StreamEnvelope = root.lookupType("heart.beats.streaming.StreamEnvelope");
const textDecoder = new TextDecoder("utf-8");

type DecodedFrameEnvelope = {
  png_data?: Uint8Array;
  pngData?: Uint8Array;
};

type DecodedPeripheralEnvelope = {
  peripheral_info?: unknown;
  peripheralInfo?: unknown;
  payload?: Uint8Array;
  payload_encoding?: number;
  payloadEncoding?: number;
};

function normalizePeripheralInfo(raw: unknown): PeripheralInfo {
  if (!raw || typeof raw !== "object") {
    return { id: null, tags: [] };
  }
  const info = raw as { id?: string; tags?: PeripheralTag[] };
  return {
    id: info.id || null,
    tags: info.tags ?? [],
  };
}

function getFrameBytes(frame: DecodedFrameEnvelope | null | undefined) {
  return frame?.pngData ?? frame?.png_data ?? null;
}

function getPeripheralInfo(
  peripheral: DecodedPeripheralEnvelope | null | undefined,
) {
  return peripheral?.peripheralInfo ?? peripheral?.peripheral_info ?? null;
}

function getPayloadEncoding(
  peripheral: DecodedPeripheralEnvelope | null | undefined,
) {
  return peripheral?.payloadEncoding ?? peripheral?.payload_encoding ?? null;
}

export function decodeStreamEvent(buffer: ArrayBuffer): StreamEvent | null {
  const envelope = StreamEnvelope.decode(new Uint8Array(buffer)) as {
    frame?: DecodedFrameEnvelope | null;
    peripheral?: DecodedPeripheralEnvelope | null;
  };
  const pngData = getFrameBytes(envelope.frame);

  if (pngData) {
    return {
      type: "frame",
      payload: {
        pngData,
      },
    };
  }

  if (envelope.peripheral?.payload) {
    let data: unknown = null;
    const payloadEncoding = getPayloadEncoding(envelope.peripheral);
    if (payloadEncoding === 1) {
      try {
        data = JSON.parse(textDecoder.decode(envelope.peripheral.payload));
      } catch {
        data = null;
      }
    }
    return {
      type: "peripheral",
      payload: {
        peripheralInfo: normalizePeripheralInfo(
          getPeripheralInfo(envelope.peripheral),
        ),
        data,
        payloadEncoding,
      },
    };
  }

  return null;
}
