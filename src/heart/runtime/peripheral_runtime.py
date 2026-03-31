from __future__ import annotations

from typing import Any

from heart.device.beats import WebSocket
from heart.peripheral.core import (PeripheralInfo, PeripheralMessageEnvelope,
                                   PeripheralTag)
from heart.peripheral.core.input import InputDebugEnvelope
from heart.peripheral.core.manager import PeripheralManager
from heart.utilities.logging import get_logger
from heart.utilities.reactivex_threads import drain_frame_thread_queue

logger = get_logger(__name__)
INPUT_DEBUG_STAGE_TAG = "input_debug_stage"
INPUT_DEBUG_STREAM_TAG = "input_debug_stream"


class PeripheralRuntime:
    """Manage peripheral lifecycle and event streaming for the runtime."""

    def __init__(self, peripheral_manager: PeripheralManager) -> None:
        self._peripheral_manager = peripheral_manager

    def detect_and_start(self) -> None:
        logger.info("Attempting to detect attached peripherals")
        self._peripheral_manager.detect()
        peripherals = self._peripheral_manager.peripherals
        logger.info(
            "Detected attached peripherals - found %d. peripherals=%s",
            len(peripherals),
            peripherals,
        )
        logger.info("Starting all peripherals")
        self._peripheral_manager.start()

    def configure_streaming(self, websocket: WebSocket | None = None) -> None:
        ws = websocket or WebSocket()
        self._peripheral_manager.debug_tap.observable().subscribe(
            on_next=lambda envelope: ws.send(
                kind="peripheral",
                payload=self._streaming_envelope(envelope),
            ),
        )

    def _streaming_envelope(
        self, envelope: InputDebugEnvelope
    ) -> PeripheralMessageEnvelope[dict[str, Any]]:
        return PeripheralMessageEnvelope(
            peripheral_info=PeripheralInfo(
                id=envelope.source_id,
                tags=(
                    PeripheralTag(
                        name=INPUT_DEBUG_STAGE_TAG,
                        variant=envelope.stage.value,
                    ),
                    PeripheralTag(
                        name=INPUT_DEBUG_STREAM_TAG,
                        variant=envelope.stream_name,
                    ),
                ),
            ),
            data=envelope.as_dict(),
        )

    def tick(self) -> None:
        drain_frame_thread_queue()
        if self._peripheral_manager.clock.value is None:
            return
        self._peripheral_manager.frame_tick_controller.advance(
            self._peripheral_manager.clock.value
        )
        self._peripheral_manager.game_tick.on_next(True)
