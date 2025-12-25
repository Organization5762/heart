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

export function decodeStreamEvent(buffer: ArrayBuffer): StreamEvent | null {
  const envelope = StreamEnvelope.decode(new Uint8Array(buffer)) as {
    frame?: { png_data?: Uint8Array } | null;
    peripheral?: {
      peripheral_info?: unknown;
      payload?: Uint8Array;
      payload_encoding?: number;
    } | null;
  };

  if (envelope.frame?.png_data) {
    return {
      type: "frame",
      payload: {
        pngData: envelope.frame.png_data,
      },
    };
  }

  if (envelope.peripheral?.payload) {
    let data: unknown = null;
    const payloadEncoding = envelope.peripheral.payload_encoding ?? null;
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
        peripheralInfo: normalizePeripheralInfo(envelope.peripheral.peripheral_info),
        data,
        payloadEncoding,
      },
    };
  }

  return null;
}
