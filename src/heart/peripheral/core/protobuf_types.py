from __future__ import annotations

from enum import StrEnum

from heart.peripheral.core.protobuf_catalog import (
    PERIPHERAL_INPUT_PACKAGE, PERIPHERAL_PAYLOADS_PACKAGE)

INPUT_EVENT_TYPE = f"{PERIPHERAL_INPUT_PACKAGE}.InputEvent"
PERIPHERAL_STATUS_TYPE = f"{PERIPHERAL_PAYLOADS_PACKAGE}.PeripheralStatus"


class PeripheralPayloadType(StrEnum):
    INPUT_EVENT = INPUT_EVENT_TYPE
    PERIPHERAL_STATUS = PERIPHERAL_STATUS_TYPE
