# Beats websocket protobuf streaming

## Purpose

Define the protobuf envelope used to stream frames and peripheral updates into the Beats UI and document how the client decodes binary websocket messages.

## Sources

- `src/heart/device/beats/websocket.py`
- `src/heart/peripheral/core/encoding.py`
- `src/heart/device/beats/proto/beats_streaming.proto`
- `experimental/beats/src/actions/ws/protocol.ts`

## Materials

- `protobuf` runtime for Python message serialization.
- `protobufjs` for decoding the protobuf envelope in the Beats UI.

## Message layout

`StreamEnvelope` wraps the payload in a `oneof` so clients can switch on the message type without JSON parsing:

- `frame`: contains raw PNG bytes in `png_data`.
- `peripheral`: includes `PeripheralInfo`, an encoded payload, a payload encoding enum, and an optional payload type string for protobuf payloads. `encode_peripheral_payload` in `heart.peripheral.core.encoding` centralizes the encoding logic so other integrations can reuse the same protobuf-aware rules.

## Client decoding

The Beats UI uses `protobufjs` to parse `StreamEnvelope` frames and emits a typed `StreamEvent` into the RxJS stream. Frame bytes are converted directly into PNG blobs, and peripheral payloads are decoded from UTF-8 JSON when the payload encoding signals `JSON_UTF8`. Protobuf payloads set `payload_type` to the fully-qualified message name and set the encoding to `PROTOBUF`.

## Python decoding helpers

`heart.device.beats.websocket.decode_stream_envelope` provides the Python mirror for decoding envelopes. It returns a `(kind, payload)` tuple for `frame` and `peripheral` payloads, and uses `decode_peripheral_payload` from `heart.peripheral.core.encoding` to decode JSON or protobuf payload bytes. Protobuf decoding resolves the `payload_type` with `google.protobuf.symbol_database.Default()`. The `heart.peripheral.core.protobuf_registry` helper can import modules registered to a package prefix when a symbol is missing, and `heart.device.beats.proto` registers the Beats package prefix so decoding can succeed without manual imports.
