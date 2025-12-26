"""Protocol buffer modules for Beats streaming."""

from heart.peripheral.core.protobuf_registry import protobuf_registry

STREAMING_PROTO_PACKAGE = "heart.beats.streaming"
STREAMING_PROTO_MODULE = "heart.device.beats.proto.beats_streaming_pb2"

protobuf_registry.register_type_prefix(STREAMING_PROTO_PACKAGE, STREAMING_PROTO_MODULE)
