# Beats websocket protobuf streaming

## Purpose

Define the protobuf envelope used to stream frames and peripheral updates into the Beats UI and document how the client decodes binary websocket messages.

## Sources

- `src/heart/device/beats/websocket.py`
- `src/heart/device/beats/proto/beats_streaming.proto`
- `experimental/beats/src/actions/ws/protocol.ts`

## Materials

- `protobuf` runtime for Python message serialization.
- `protobufjs` for decoding the protobuf envelope in the Beats UI.

## Message layout

`StreamEnvelope` wraps the payload in a `oneof` so clients can switch on the message type without JSON parsing:

- `frame`: contains raw PNG bytes in `png_data`.
- `peripheral`: includes `PeripheralInfo`, an encoded payload, and a payload encoding enum.

## Client decoding

The Beats UI uses `protobufjs` to parse `StreamEnvelope` frames and emits a typed `StreamEvent` into the RxJS stream. Frame bytes are converted directly into PNG blobs, and peripheral payloads are decoded from UTF-8 JSON when the payload encoding signals `JSON_UTF8`.
