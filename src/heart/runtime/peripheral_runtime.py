from __future__ import annotations

import base64
import io
from queue import Empty, SimpleQueue
from typing import Any

import pygame
from manyfold import drain_frame_thread_queue
from PIL import Image, ImageOps

from heart import DeviceDisplayMode
from heart.device.beats.websocket import WebSocket
from heart.peripheral.core import (PeripheralInfo, PeripheralMessageEnvelope,
                                   PeripheralTag)
from heart.peripheral.core.input import InputDebugEnvelope
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers.free_text import FreeTextRenderer
from heart.renderers.image import (ContainRenderImage,
                                   SurfaceRenderImageStateProvider)
from heart.runtime.active_game_loop import get_active_game_loop
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)
INPUT_DEBUG_STAGE_TAG = "input_debug_stage"
INPUT_DEBUG_STREAM_TAG = "input_debug_stream"
CONTROL_COMMAND_BROWSE = "browse"
CONTROL_COMMAND_ACTIVATE = "activate"
CONTROL_COMMAND_ALTERNATE = "alternate_activate"
CONTROL_COMMAND_SENSOR_UPDATE = "sensor_update"
CONTROL_COMMAND_TEXT_UPDATE = "text_update"
CONTROL_COMMAND_IMAGE_UPDATE = "image_update"
PHONE_TEXT_DISPLAY_DURATION_SECONDS = 5.0
PHONE_IMAGE_DISPLAY_DURATION_SECONDS = 5.0


class PeripheralRuntime:
    """Manage peripheral lifecycle and event streaming for the runtime."""

    def __init__(self, peripheral_manager: PeripheralManager) -> None:
        self._peripheral_manager = peripheral_manager
        self._control_messages: SimpleQueue[Any] = SimpleQueue()
        self._frame_clock: pygame.time.Clock | None = None

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

    def configure_streaming(self, websocket: Any | None = None) -> None:
        if (
            websocket is None
            and not Configuration.forward_to_beats_app()
            and not Configuration.beats_websocket_enabled()
        ):
            logger.debug("Beats streaming disabled; skipping websocket startup")
            return

        ws = websocket or _build_websocket()
        ws.set_control_handler(self._handle_control_message)
        if not Configuration.stream_beats_input_debug():
            logger.debug("Beats input debug streaming disabled")
            return

        self._peripheral_manager.input_io.debug_tap.observable().subscribe(
            on_next=lambda envelope: ws.send(
                kind="peripheral",
                payload=self._streaming_envelope(envelope),
            ),
        )

    def _handle_control_message(self, control_message: Any) -> None:
        self._control_messages.put(control_message)

    def _drain_control_messages(self) -> None:
        while True:
            try:
                control_message = self._control_messages.get_nowait()
            except Empty:
                return
            self._apply_control_message(control_message)

    def _apply_control_message(self, control_message: Any) -> None:
        navigation = self._peripheral_manager.input_io.navigation
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
            external_sensor_hub = self._peripheral_manager.input_io.external_sensors
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
            return
        if control_message.command == CONTROL_COMMAND_TEXT_UPDATE:
            self._present_phone_text_renderer(
                text=None if control_message.clear else control_message.text
            )
            return
        if control_message.command == CONTROL_COMMAND_IMAGE_UPDATE:
            self._present_phone_image_renderer(
                image_base64=control_message.image_base64,
            )
            return

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

    def _present_phone_text_renderer(self, text: str | None) -> None:
        loop = get_active_game_loop()
        if loop is None:
            logger.debug("No active GameLoop available for phone text display.")
            return

        if not text:
            loop.clear_temporary_renderer()
            return

        renderer = FreeTextRenderer()
        renderer.set_text(text)
        loop.present_temporary_renderer(
            renderer,
            duration_seconds=PHONE_TEXT_DISPLAY_DURATION_SECONDS,
        )

    def _present_phone_image_renderer(
        self,
        image_base64: str | None,
    ) -> None:
        loop = get_active_game_loop()
        if loop is None:
            logger.debug("No active GameLoop available for phone image display.")
            return

        if not image_base64:
            loop.clear_temporary_renderer()
            return

        try:
            image_bytes = base64.b64decode(image_base64, validate=True)
            with Image.open(io.BytesIO(image_bytes)) as uploaded_image:
                normalized = ImageOps.exif_transpose(uploaded_image).convert("RGBA")
                surface = pygame.image.fromstring(
                    normalized.tobytes(),
                    normalized.size,
                    normalized.mode,
                ).convert_alpha()
        except Exception:
            logger.exception("Failed to decode phone image payload.")
            return

        renderer = ContainRenderImage(
            provider=SurfaceRenderImageStateProvider(base_image=surface)
        )
        renderer.device_display_mode = DeviceDisplayMode.MIRRORED
        loop.present_temporary_renderer(
            renderer,
            duration_seconds=PHONE_IMAGE_DISPLAY_DURATION_SECONDS,
        )

    def poll(self) -> None:
        drain_frame_thread_queue()
        self._drain_control_messages()

    def set_clock(self, clock: pygame.time.Clock | None) -> None:
        self._frame_clock = clock

    def advance_frame(self, clock: pygame.time.Clock | None = None) -> None:
        if clock is not None:
            self._frame_clock = clock
        if self._frame_clock is None:
            return
        self._peripheral_manager.input_io.frame_ticks.advance(self._frame_clock)

    def tick(self) -> None:
        self.poll()
        self.advance_frame()


def _build_websocket() -> Any:
    """Construct the Beats websocket only when streaming is enabled."""

    return WebSocket()
