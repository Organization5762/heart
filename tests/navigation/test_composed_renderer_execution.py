"""Validate serial and parallel execution semantics for composed renderer graphs."""

from __future__ import annotations

import threading
import time

import pygame
import pytest

from heart import DeviceDisplayMode
from heart.device import Device, Orientation
from heart.navigation import ComposedRenderer, ComposedRendererExecutionMode
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.runtime.display_context import DisplayContext

DEFAULT_RENDER_DELAY_SECONDS = 0.05


class _FillRenderer(StatefulBaseRenderer[int]):
    """Fill renderer that records lifecycle hooks so composed execution can be asserted precisely."""

    def __init__(
        self,
        color: tuple[int, int, int, int],
        *,
        delay_seconds: float = 0.0,
        can_render_in_parallel: bool = True,
        display_mode: DeviceDisplayMode = DeviceDisplayMode.MIRRORED,
    ) -> None:
        super().__init__()
        self._can_render_in_parallel = can_render_in_parallel
        self.color = color
        self.delay_seconds = delay_seconds
        self.device_display_mode = display_mode
        self.initialize_calls = 0
        self.process_calls = 0
        self.reset_calls = 0
        self.thread_names: list[str] = []
        self._thread_names_lock = threading.Lock()

    def _create_initial_state(
        self,
        *_args,
        **_kwargs,
    ) -> int:
        self.initialize_calls += 1
        return 0

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        del orientation
        self.process_calls += 1
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        with self._thread_names_lock:
            self.thread_names.append(threading.current_thread().name)
        window.fill(self.color)

    def can_render_in_parallel(self) -> bool:
        return self._can_render_in_parallel and super().can_render_in_parallel()

    def reset(self) -> None:
        self.reset_calls += 1


def _build_display_context(device: Device) -> DisplayContext:
    screen = pygame.Surface(device.scaled_display_size(), pygame.SRCALPHA)
    return DisplayContext(
        device=device,
        screen=screen,
        clock=pygame.time.Clock(),
    )


def _process_composed_renderer(
    renderer: ComposedRenderer,
    display_context: DisplayContext,
    peripheral_manager: PeripheralManager,
    orientation: Orientation,
) -> None:
    renderer.initialize(display_context, peripheral_manager, orientation)
    renderer._internal_process(display_context, peripheral_manager, orientation)


class TestComposedRendererExecution:
    """Ensure composed renderer execution modes preserve layering, fallback, and reset semantics."""

    def test_serial_mode_initializes_once_and_preserves_order(
        self,
        device: Device,
        manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        """Verify serial execution initializes children once and preserves list order so layered scenes remain deterministic."""
        display_context = _build_display_context(device)
        lower = _FillRenderer((255, 0, 0, 255))
        upper = _FillRenderer((0, 0, 255, 255))
        composed = ComposedRenderer(
            renderers=[lower, upper],
            execution_mode=ComposedRendererExecutionMode.SERIAL,
        )

        _process_composed_renderer(composed, display_context, manager, orientation)
        composed._internal_process(display_context, manager, orientation)

        assert lower.initialize_calls == 1
        assert upper.initialize_calls == 1
        assert lower.process_calls == 2
        assert upper.process_calls == 2
        assert display_context.screen.get_at((0, 0)) == pygame.Color(0, 0, 255, 255)

    def test_parallel_mode_processes_children_off_main_thread_and_preserves_order(
        self,
        device: Device,
        manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        """Verify parallel execution runs child rendering off the main thread while preserving input layering for overlay correctness."""
        display_context = _build_display_context(device)
        lower = _FillRenderer(
            (255, 0, 0, 255),
            delay_seconds=DEFAULT_RENDER_DELAY_SECONDS,
        )
        upper = _FillRenderer((0, 0, 255, 255))
        composed = ComposedRenderer(
            renderers=[lower, upper],
            execution_mode=ComposedRendererExecutionMode.PARALLEL,
        )

        _process_composed_renderer(composed, display_context, manager, orientation)

        assert lower.thread_names[-1].startswith("composed-renderer")
        assert upper.thread_names[-1].startswith("composed-renderer")
        assert display_context.screen.get_at((0, 0)) == pygame.Color(0, 0, 255, 255)

    @pytest.mark.parametrize(
        ("renderer", "expected_name"),
        [
            (
                _FillRenderer(
                    (255, 0, 0, 255),
                    can_render_in_parallel=False,
                ),
                "_FillRenderer",
            ),
            (
                _FillRenderer(
                    (255, 0, 0, 255),
                    display_mode=DeviceDisplayMode.OPENGL,
                ),
                "_FillRenderer",
            ),
        ],
        ids=["explicitly-unsafe", "opengl-renderer"],
    )
    def test_parallel_mode_falls_back_to_serial_for_unsafe_children(
        self,
        device: Device,
        manager: PeripheralManager,
        orientation: Orientation,
        renderer: _FillRenderer,
        expected_name: str,
    ) -> None:
        """Verify parallel mode falls back to serial when any child is unsafe so nested graphs avoid thread-unsafe render paths."""
        display_context = _build_display_context(device)
        safe = _FillRenderer((0, 0, 255, 255))
        composed = ComposedRenderer(
            renderers=[renderer, safe],
            execution_mode=ComposedRendererExecutionMode.PARALLEL,
        )

        _process_composed_renderer(composed, display_context, manager, orientation)

        assert renderer.thread_names[-1] == "MainThread"
        assert safe.thread_names[-1] == "MainThread"
        assert expected_name in composed._parallel_blockers()

    def test_nested_serial_parent_can_host_parallel_child_group(
        self,
        device: Device,
        manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        """Verify a serial parent can host a parallel child group so graph nesting can express overlay barriers without new APIs."""
        display_context = _build_display_context(device)
        parallel_group = ComposedRenderer(
            renderers=[
                _FillRenderer((255, 0, 0, 255)),
                _FillRenderer((0, 255, 0, 255)),
            ],
            execution_mode=ComposedRendererExecutionMode.PARALLEL,
        )
        overlay = _FillRenderer((0, 0, 255, 255))
        root = ComposedRenderer(
            renderers=[parallel_group, overlay],
            execution_mode=ComposedRendererExecutionMode.SERIAL,
        )

        _process_composed_renderer(root, display_context, manager, orientation)

        assert display_context.screen.get_at((0, 0)) == pygame.Color(0, 0, 255, 255)

    def test_nested_parallel_parent_can_host_serial_child_groups(
        self,
        device: Device,
        manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        """Verify a parallel parent can host serial child groups so nested trees can mix execution modes without flattening away barriers."""
        display_context = _build_display_context(device)
        first_group = ComposedRenderer(
            renderers=[
                _FillRenderer((255, 0, 0, 255)),
                _FillRenderer((0, 255, 0, 255)),
            ],
            execution_mode=ComposedRendererExecutionMode.SERIAL,
        )
        second_group = ComposedRenderer(
            renderers=[
                _FillRenderer((0, 0, 255, 255)),
                _FillRenderer((255, 255, 0, 255)),
            ],
            execution_mode=ComposedRendererExecutionMode.SERIAL,
        )
        root = ComposedRenderer(
            renderers=[first_group, second_group],
            execution_mode=ComposedRendererExecutionMode.PARALLEL,
        )

        _process_composed_renderer(root, display_context, manager, orientation)

        assert display_context.screen.get_at((0, 0)) == pygame.Color(255, 255, 0, 255)

    def test_reset_propagates_to_nested_children(
        self,
        device: Device,
        manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        """Verify reset propagates through nested composed graphs so mode switches leave no stale renderer state behind."""
        display_context = _build_display_context(device)
        child_one = _FillRenderer((255, 0, 0, 255))
        child_two = _FillRenderer((0, 0, 255, 255))
        nested = ComposedRenderer(
            renderers=[child_one],
            execution_mode=ComposedRendererExecutionMode.PARALLEL,
        )
        root = ComposedRenderer(
            renderers=[nested, child_two],
            execution_mode=ComposedRendererExecutionMode.SERIAL,
        )

        _process_composed_renderer(root, display_context, manager, orientation)
        root.reset()

        assert child_one.reset_calls == 1
        assert child_two.reset_calls == 1
