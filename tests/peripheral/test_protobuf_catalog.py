from __future__ import annotations

import pytest

from heart.peripheral.core.protobuf_registry import (protobuf_registry,
                                                     protobuf_symbol_database)
from heart.peripheral.core.protobuf_types import PeripheralPayloadType

PERIPHERAL_STATUS_TYPE = PeripheralPayloadType.PERIPHERAL_STATUS


class TestProtobufCatalog:
    """Validate catalog-driven protobuf registration so decoding stays consistent."""

    def test_resolves_catalog_payload_type(self) -> None:
        """Verify catalog entries load protobuf modules so peripheral payloads decode without manual imports."""
        try:
            protobuf_symbol_database.GetSymbol(PERIPHERAL_STATUS_TYPE.value)
        except KeyError:
            pass
        else:
            pytest.fail(
                "PeripheralStatus symbol is already registered, invalidating the test."
            )

        message_class = protobuf_registry.get_message_class(PERIPHERAL_STATUS_TYPE)

        assert message_class is not None
        message = message_class(peripheral_id="sensor-1", status="ready")
        assert message.peripheral_id == "sensor-1"
        assert message.status == "ready"
