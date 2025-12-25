from __future__ import annotations

from dataclasses import dataclass

from lagom import Container

from heart.device import Device
from heart.navigation import AppController
from heart.peripheral.core.manager import PeripheralManager
from heart.runtime.display_context import DisplayContext
from heart.runtime.frame_presenter import FramePresenter
from heart.runtime.peripheral_runtime import PeripheralRuntime
from heart.runtime.pygame_event_handler import PygameEventHandler
from heart.runtime.render_pipeline import RendererVariant, RenderPipeline


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
    device: Device,
    render_variant: RendererVariant,
) -> GameLoopComponents:
    peripheral_manager = resolver.resolve(PeripheralManager)
    display = DisplayContext(device=device)
    render_pipeline = RenderPipeline(
        device=device,
        peripheral_manager=peripheral_manager,
        render_variant=render_variant,
    )
    frame_presenter = FramePresenter(
        device=device,
        display=display,
        render_pipeline=render_pipeline,
    )
    peripheral_runtime = PeripheralRuntime(peripheral_manager)
    return GameLoopComponents(
        app_controller=AppController(),
        display=display,
        render_pipeline=render_pipeline,
        frame_presenter=frame_presenter,
        event_handler=PygameEventHandler(),
        peripheral_manager=peripheral_manager,
        peripheral_runtime=peripheral_runtime,
    )
