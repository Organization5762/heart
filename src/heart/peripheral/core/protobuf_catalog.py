from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from heart.peripheral.core.protobuf_registry import ProtobufTypeRegistry

BEATS_STREAMING_PACKAGE = "heart.beats.streaming"
BEATS_STREAMING_MODULE = "heart.device.beats.proto.beats_streaming_pb2"
PERIPHERAL_PAYLOADS_PACKAGE = "heart.peripheral.payloads"
PERIPHERAL_PAYLOADS_MODULE = "heart.peripheral.proto.peripheral_payloads_pb2"
PERIPHERAL_INPUT_PACKAGE = "heart.peripheral.input"
PERIPHERAL_INPUT_MODULE = "heart.peripheral.proto.input_events_pb2"


@dataclass(frozen=True, slots=True)
class ProtobufCatalogEntry:
    package_prefix: str
    module_path: str
    description: str


PROTOBUF_CATALOG: tuple[ProtobufCatalogEntry, ...] = (
    ProtobufCatalogEntry(
        package_prefix=BEATS_STREAMING_PACKAGE,
        module_path=BEATS_STREAMING_MODULE,
        description="Beats websocket streaming envelopes.",
    ),
    ProtobufCatalogEntry(
        package_prefix=PERIPHERAL_PAYLOADS_PACKAGE,
        module_path=PERIPHERAL_PAYLOADS_MODULE,
        description="Core peripheral payload schemas.",
    ),
    ProtobufCatalogEntry(
        package_prefix=PERIPHERAL_INPUT_PACKAGE,
        module_path=PERIPHERAL_INPUT_MODULE,
        description="Peripheral input event payloads.",
    ),
)


def register_protobuf_catalog(registry: ProtobufTypeRegistry) -> None:
    for entry in PROTOBUF_CATALOG:
        registry.register_type_prefix(entry.package_prefix, entry.module_path)
