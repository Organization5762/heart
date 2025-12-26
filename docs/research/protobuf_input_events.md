# Protobuf input event payloads

## Purpose

Document the protobuf payload used to serialize `heart.peripheral.core.Input` events so peripheral streams can emit binary payloads without bespoke encoding logic.

## Sources

- `src/heart/peripheral/core/encoding.py`
- `src/heart/peripheral/core/protobuf_catalog.py`
- `src/heart/peripheral/proto/input_events.proto`
- `src/heart/peripheral/proto/input_events_pb2.py`

## Materials

- Python `protobuf` runtime for message serialization.
- `protoc` for generating `*_pb2.py` modules.

## Notes

`heart.peripheral.core.encoding.encode_peripheral_payload` now emits a protobuf `InputEvent` message when it receives a `heart.peripheral.core.Input` instance. The schema stores the input `event_type`, an ISO-8601 timestamp string, and a UTF-8 JSON payload in `data_json`. `heart.peripheral.core.protobuf_catalog` registers the `heart.peripheral.input` package so `decode_peripheral_payload` can resolve `InputEvent` without manual imports.
