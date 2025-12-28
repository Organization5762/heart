from __future__ import annotations

from dataclasses import dataclass

from heart.navigation import AppController
from heart.peripheral.core.manager import PeripheralManager
from heart.runtime.display_context import DisplayContext
from heart.runtime.frame.presenter import FramePresenter
from heart.runtime.game_loop.event_handler import PygameEventHandler
from heart.runtime.peripheral_runtime import PeripheralRuntime
from heart.runtime.render.pipeline import RenderPipeline


@dataclass(frozen=True)
class GameLoopComponents:
    app_controller: AppController
    display: DisplayContext
    render_pipeline: RenderPipeline
    frame_presenter: FramePresenter
    event_handler: PygameEventHandler
    peripheral_manager: PeripheralManager
    peripheral_runtime: PeripheralRuntime
