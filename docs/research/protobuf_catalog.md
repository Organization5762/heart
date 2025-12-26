# Protobuf catalog integration notes

## Problem statement

Protobuf payload decoding relied on ad hoc package registration, which made it easy to miss new schema modules when adding peripherals. The runtime needed a single catalog that registers protobuf packages and keeps decoding logic consistent.

## Materials

- `src/heart/peripheral/core/protobuf_catalog.py`
- `src/heart/peripheral/core/protobuf_registry.py`
- `src/heart/peripheral/core/encoding.py`
- `src/heart/device/beats/proto/beats_streaming.proto`
- `src/heart/peripheral/proto/peripheral_payloads.proto`
- `scripts/generate_protobuf.py`
- `docs/beats-websocket-protobuf.md`

## Notes

- The catalog registers package prefixes with `protobuf_registry` at import time, keeping protobuf type resolution centralized.
- `protobuf_registry` still imports module paths on demand when a payload type is unknown, so decode paths stay lazy while the catalog remains declarative.
- The `scripts/generate_protobuf.py` helper provides a repeatable entry point for regenerating `*_pb2.py` modules after schema updates.

## Impact

- New protobuf schemas are added by updating `PROTOBUF_CATALOG` and regenerating code, without manual imports in every call site.
- Tests can resolve protobuf payloads using the catalog to validate registry behavior for non-Beats payloads.
