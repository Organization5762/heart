from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import StrEnum

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.runtime.display_context import DisplayContext
from heart.runtime.rendering.renderer_processor import RendererProcessor
from heart.runtime.rendering.surface.collection import RenderSurfaceCollector
from heart.runtime.rendering.surface.merge import SurfaceCompositionManager
from heart.runtime.rendering.surface.provider import RendererSurfaceProvider
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

from .renderer_specs import (RendererResolver, RendererSpec,
                             resolve_renderer_spec)

logger = get_logger(__name__)

DEFAULT_COMPOSED_RENDERER_EXECUTION_MODE = "serial"
COMPOSED_RENDERER_THREAD_NAME_PREFIX = "composed-renderer"


class ComposedRendererExecutionMode(StrEnum):
    SERIAL = "serial"
    PARALLEL = "parallel"


@dataclass
class ComposedRendererState:
    peripheral_manager: PeripheralManager
    window: DisplayContext
    orientation: Orientation


class ComposedRenderer(StatefulBaseRenderer[ComposedRendererState]):
    def __init__(
        self,
        renderers: list[RendererSpec] | None = None,
        surface_provider: RendererSurfaceProvider | None = None,
        execution_mode: ComposedRendererExecutionMode = (
            ComposedRendererExecutionMode(DEFAULT_COMPOSED_RENDERER_EXECUTION_MODE)
        ),
    ) -> None:
        super().__init__()
        self._renderer_resolver = getattr(surface_provider, "_container", None)
        self._composition_manager = SurfaceCompositionManager()
        self._render_executor: ThreadPoolExecutor | None = None
        self.execution_mode = execution_mode
        self.surface_provider = surface_provider
        self.renderers = [
            resolve_renderer_spec(renderer, self._renderer_resolver)
            for renderer in (renderers or [])
        ]
        self._refresh_device_display_mode()

    def _real_get_renderers(self) -> list[StatefulBaseRenderer]:
        return [self]

    @property
    def name(self) -> str:
        joined = "+".join(renderer.name for renderer in self.renderers)
        return f"ComposedRenderer:{joined}"

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> ComposedRendererState:
        for renderer in self.renderers:
            renderer.initialize(window, peripheral_manager, orientation)
        return ComposedRendererState(
            peripheral_manager=peripheral_manager,
            window=window,
            orientation=orientation,
        )

    def add_renderer(self, *renderers: RendererSpec) -> None:
        resolved_renderers = [
            resolve_renderer_spec(renderer, self._renderer_resolver)
            for renderer in renderers
        ]
        self.renderers.extend(resolved_renderers)
        self._refresh_device_display_mode()
        if self.is_initialized():
            for item in resolved_renderers:
                item.initialize(
                    self.state.window,
                    self.state.peripheral_manager,
                    self.state.orientation,
                )

    def resolve_renderer(
        self, resolver: RendererResolver, renderer: type[StatefulBaseRenderer]
    ) -> None:
        resolved = resolver.resolve(renderer)
        self.renderers.append(resolved)
        self._refresh_device_display_mode()
        if self.is_initialized():
            resolved.initialize(
                self.state.window,
                self.state.peripheral_manager,
                self.state.orientation,
            )

    def resolve_renderer_from_container(
        self, renderer: type[StatefulBaseRenderer]
    ) -> None:
        self.add_renderer(renderer)

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        collector = RenderSurfaceCollector(
            self._build_renderer_processor(window).process_renderer,
            self._get_render_executor,
        )
        rendered_surfaces = collector.collect(
            self.renderers,
            parallel=self._should_render_in_parallel(),
        )
        composite = self._composition_manager.compose_serial(rendered_surfaces)
        if composite is not None:
            window.blit(composite, (0, 0))

    def reset(self) -> None:
        self._shutdown_render_executor()
        for renderer in self.renderers:
            renderer.reset()
        super().reset()

    def _build_renderer_processor(
        self,
        window: DisplayContext,
    ) -> RendererProcessor:
        return RendererProcessor(window, self.state.peripheral_manager)

    def _get_render_executor(self) -> ThreadPoolExecutor:
        if self._render_executor is None:
            self._render_executor = ThreadPoolExecutor(
                max_workers=Configuration.render_executor_max_workers(),
                thread_name_prefix=COMPOSED_RENDERER_THREAD_NAME_PREFIX,
            )
        return self._render_executor

    def _parallel_blockers(self) -> list[str]:
        return [
            renderer.name
            for renderer in self.renderers
            if not renderer.can_render_in_parallel()
        ]

    def _refresh_device_display_mode(self) -> None:
        if any(
            renderer.device_display_mode == DeviceDisplayMode.OPENGL
            for renderer in self.renderers
        ):
            self.device_display_mode = DeviceDisplayMode.OPENGL
            return
        self.device_display_mode = DeviceDisplayMode.FULL

    def _should_render_in_parallel(self) -> bool:
        if self.execution_mode is not ComposedRendererExecutionMode.PARALLEL:
            return False
        blockers = self._parallel_blockers()
        if not blockers:
            return True
        logger.debug(
            "Composed renderer falling back to serial execution",
            extra={
                "renderer": self.name,
                "blocking_renderers": blockers,
                "execution_mode": self.execution_mode.value,
            },
        )
        return False

    def _shutdown_render_executor(self) -> None:
        if self._render_executor is None:
            return
        self._render_executor.shutdown(wait=True)
        self._render_executor = None
