import logging
from collections.abc import Callable

import pygame

from heart.assets.loader import Loader
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.switch import SwitchState
from heart.renderers.spritesheet_random.state import (
    LoopPhase, SpritesheetLoopRandomState)

logger = logging.getLogger(__name__)


class SpritesheetLoopRandomProvider:
    def __init__(self, sheet_file_path: str) -> None:
        self.file = sheet_file_path

    def create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
        initial_phase: LoopPhase,
        update_switch_state: Callable[[SwitchState | None], None],
    ) -> SpritesheetLoopRandomState:
        def new_switch_state(value: SwitchState | None) -> None:
            update_switch_state(value)

        source = peripheral_manager.get_main_switch_subscription()
        source.subscribe(
            on_next=new_switch_state,
            on_error=lambda exc: logger.error("Error Occurred: %s", exc),
        )
        return SpritesheetLoopRandomState(
            phase=initial_phase,
            spritesheet=Loader.load_spirtesheet(self.file),
            switch_state=None,
        )
