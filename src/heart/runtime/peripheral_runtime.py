from __future__ import annotations

from typing import Any

from heart.device.beats import WebSocket
from heart.device.beats.websocket import (CONTROL_COMMAND_ACTIVATE,
                                          CONTROL_COMMAND_ALTERNATE,
                                          CONTROL_COMMAND_BROWSE,
                                          CONTROL_COMMAND_SENSOR_UPDATE,
                                          ControlMessage)
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
        ws.set_control_handler(self._handle_control_message)
        self._peripheral_manager.debug_tap.observable().subscribe(
            on_next=lambda envelope: ws.send(
                kind="peripheral",
                payload=self._streaming_envelope(envelope),
            ),
        )

    def _handle_control_message(self, control_message: ControlMessage) -> None:
        navigation = self._peripheral_manager.navigation_profile
        if control_message.command == CONTROL_COMMAND_BROWSE:
            navigation.inject_browse(
                control_message.browse_step,
                source="beats.control.browse",
            )
            return
        if control_message.command == CONTROL_COMMAND_ACTIVATE:
            navigation.inject_activate(source="beats.control.activate")
            return
        if control_message.command == CONTROL_COMMAND_ALTERNATE:
            navigation.inject_alternate_activate(
                source="beats.control.alternate",
            )
            return
        if control_message.command == CONTROL_COMMAND_SENSOR_UPDATE:
            external_sensor_hub = self._peripheral_manager.external_sensor_hub
            sensor_key = control_message.sensor_key
            if sensor_key is None:
                return
            try:
                if control_message.clear:
                    external_sensor_hub.clear_value(sensor_key)
                    return
                sensor_value = control_message.sensor_value
                if sensor_value is None:
                    return
                external_sensor_hub.set_value(sensor_key, sensor_value)
            except ValueError:
                logger.warning("Ignoring invalid websocket sensor key: %s", sensor_key)

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
