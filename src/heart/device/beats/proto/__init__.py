"""Protocol buffer modules for Beats streaming."""

from heart.peripheral.core import protobuf_catalog
from heart.peripheral.core.protobuf_registry import protobuf_registry

protobuf_catalog.register_protobuf_catalog(protobuf_registry)
