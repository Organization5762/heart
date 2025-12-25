# Beats streaming protobuf envelope

## Goal

Record the protobuf schema and encoding decisions for the Beats websocket stream so the runtime and UI stay aligned on binary payloads.

## Sources

- `src/heart/device/beats/proto/beats_streaming.proto`
- `src/heart/device/beats/websocket.py`
- `experimental/beats/src/actions/ws/protocol.ts`

## Materials

- Protobuf schema file (`src/heart/device/beats/proto/beats_streaming.proto`).
- Python protobuf runtime for serialization.
- `protobufjs` for client-side decoding.

## Notes

- `StreamEnvelope` carries either a `Frame` or a `PeripheralEnvelope` in a `oneof` payload.
- Peripheral data is encoded in the protobuf envelope alongside an explicit payload encoding enum, so JSON payloads can remain stable while leaving room for future encodings.
- The Beats UI parses the envelope and maps it into typed `StreamEvent` objects for downstream providers.
