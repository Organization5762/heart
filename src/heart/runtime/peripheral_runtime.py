from __future__ import annotations

from heart.device.beats import WebSocket
from heart.peripheral.core.manager import PeripheralManager
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class PeripheralRuntime:
    """Manage peripheral lifecycle and event streaming for the runtime."""

    def __init__(self, peripheral_manager: PeripheralManager) -> None:
        self._peripheral_manager = peripheral_manager
        self._websocket: WebSocket | None = None

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
        self._websocket = ws
        self._peripheral_manager.get_event_bus().subscribe(
            on_next=lambda x: ws.send(kind="peripheral", payload=x),
        )

    def tick(self) -> None:
        self._peripheral_manager.game_tick.on_next(True)

    def shutdown(self) -> None:
        if self._websocket is None:
            return
        self._websocket.shutdown()
