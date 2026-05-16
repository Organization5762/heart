from __future__ import annotations

from enum import StrEnum

from heart.peripheral.core.protobuf_catalog import PERIPHERAL_INPUT_PACKAGE

INPUT_EVENT_TYPE = f"{PERIPHERAL_INPUT_PACKAGE}.InputEvent"


class PeripheralPayloadType(StrEnum):
    INPUT_EVENT = INPUT_EVENT_TYPE
