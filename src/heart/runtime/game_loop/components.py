from __future__ import annotations

from dataclasses import dataclass

from heart.navigation import GameModes
from heart.peripheral.core.manager import PeripheralManager
from heart.runtime.display_context import DisplayContext
from heart.runtime.game_loop.event_handler import PygameEventHandler
from heart.runtime.peripheral_runtime import PeripheralRuntime


@dataclass(frozen=True)
class GameLoopComponents:
    game_modes: GameModes
    display: DisplayContext
    event_handler: PygameEventHandler
    peripheral_manager: PeripheralManager
    peripheral_runtime: PeripheralRuntime
