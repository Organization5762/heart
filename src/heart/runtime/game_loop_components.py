from __future__ import annotations

from dataclasses import dataclass

from lagom import Container

from heart.navigation import AppController
from heart.peripheral.core.manager import PeripheralManager
from heart.runtime.display_context import DisplayContext
from heart.runtime.frame_presenter import FramePresenter
from heart.runtime.peripheral_runtime import PeripheralRuntime
from heart.runtime.pygame_event_handler import PygameEventHandler
from heart.runtime.render_pipeline import RenderPipeline


@dataclass(frozen=True)
class GameLoopComponents:
    app_controller: AppController
    display: DisplayContext
    render_pipeline: RenderPipeline
    frame_presenter: FramePresenter
    event_handler: PygameEventHandler
    peripheral_manager: PeripheralManager
    peripheral_runtime: PeripheralRuntime


def build_game_loop_components(
    resolver: Container,
) -> GameLoopComponents:
    return GameLoopComponents(
        app_controller=resolver.resolve(AppController),
        display=resolver.resolve(DisplayContext),
        render_pipeline=resolver.resolve(RenderPipeline),
        frame_presenter=resolver.resolve(FramePresenter),
        event_handler=resolver.resolve(PygameEventHandler),
        peripheral_manager=resolver.resolve(PeripheralManager),
        peripheral_runtime=resolver.resolve(PeripheralRuntime),
    )
