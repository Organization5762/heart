import logging
from collections.abc import Callable

import pygame

from heart.device import Orientation
from heart.display.color import Color
from heart.display.renderers.yolisten.state import YoListenState
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.switch import SwitchState

logger = logging.getLogger(__name__)


class YoListenStateProvider:
    def __init__(self, base_color: Color) -> None:
        self.base_color = base_color

    def create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
        on_switch_state: Callable[[SwitchState | None], None],
    ) -> YoListenState:
        def new_switch_state(value: SwitchState | None) -> None:
            on_switch_state(value)

        source = peripheral_manager.get_main_switch_subscription()
        source.subscribe(
            on_next=new_switch_state,
            on_error=lambda exc: logger.error("Error Occurred: %s", exc),
        )
        return YoListenState(color=self.base_color, switch_state=None)
