import logging
import time

import numpy as np
import pygame
import reactivex

from heart import DeviceDisplayMode
from heart.device import Orientation, Rectangle
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.slide_transition.provider import SlideTransitionProvider
from heart.renderers.slide_transition.state import (SlideTransitionMode,
                                                    SlideTransitionState)
from heart.runtime.display_context import DisplayContext
from heart.utilities.logging import get_logger
from heart.utilities.logging_control import get_logging_controller

logger = get_logger(__name__)
log_controller = get_logging_controller()


class SlideTransitionRenderer(StatefulBaseRenderer[SlideTransitionState]):
    """Slides renderer_B into view while renderer_A moves out."""

    def __init__(self, provider: SlideTransitionProvider,) -> None:
        self.provider = provider
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self._initial_state: SlideTransitionState | None = None
        self._static_mask_indices: np.ndarray | None = None
        self._static_mask_values: np.ndarray | None = None
        self._static_mask_shape: tuple[int, int] | None = None
        logger.info(f"Created SlideTransitionRenderer from {provider.renderer_a.name} and {provider.renderer_b.name}")
        super().__init__(builder=self.provider)

    def initialize(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self._initialize_children(window, peripheral_manager, orientation)
        self._initial_state = SlideTransitionState(
            peripheral_manager=peripheral_manager,
        )
        super().initialize(window, peripheral_manager, orientation)

    def state_observable(
        self, peripheral_manager: PeripheralManager
    ) -> reactivex.Observable[SlideTransitionState]:
        if self._initial_state is None:
            raise ValueError("SlideTransitionRenderer requires an initial state")
        return self.provider.observable(
            peripheral_manager,
            initial_state=self._initial_state,
        )

    def _initialize_children(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        for renderer in (self.provider.renderer_a, self.provider.renderer_b):
            if not renderer.initialized:
                renderer.initialize(
                    window=window,
                    peripheral_manager=peripheral_manager,
                    orientation=orientation,
                )
                renderer.initialized = True

    def is_done(self) -> bool:
        return not self.state.sliding

    def _render_and_log(
        self,
        renderer,
        scratch_window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
        slide_label: str,
    ) -> None:
        start_ns = time.perf_counter_ns()
        renderer._internal_process(
            scratch_window, peripheral_manager, orientation
        )
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        log_controller.log(
            key=f"render.loop.{slide_label}",
            logger=logger,
            level=logging.INFO,
            msg="renderer=%s duration_ms=%.2f",
            args=(renderer.name, duration_ms),
        )

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        state = self.state
        new_orientation = Rectangle.with_layout(1, 1)

        window_a = window.get_scratch_screen(
            orientation=new_orientation,
            display_mode=self.provider.renderer_a.device_display_mode,
        )
        window_b = window.get_scratch_screen(
            orientation=new_orientation,
            display_mode=self.provider.renderer_b.device_display_mode,
        )

        self._render_and_log(
            self.provider.renderer_a,
            window_a,
            state.peripheral_manager,
            new_orientation,
            "slide.A",
        )

        self._render_and_log(
            self.provider.renderer_b,
            window_b,
            state.peripheral_manager,
            new_orientation,
            "slide.B",
        )

        if self.provider.transition_mode is SlideTransitionMode.STATIC:
            self._render_static_transition(window, window_a, window_b)
            return
        if self.provider.transition_mode is SlideTransitionMode.GAUSSIAN:
            self._render_gaussian_transition(window, window_a, window_b)
            return

        image_width = window_a.get_width()
        offset_a = (-self.provider.direction * state.fraction_offset * image_width, 0)
        offset_b = (offset_a[0] + self.provider.direction * image_width, 0)

        window.screen.blit(window_a.screen, offset_a)
        window.screen.blit(window_b.screen, offset_b)

    def _render_static_transition(
        self,
        window: DisplayContext,
        window_a: DisplayContext,
        window_b: DisplayContext,
    ) -> None:
        array_a = pygame.surfarray.array3d(window_a.screen)
        array_b = pygame.surfarray.array3d(window_b.screen)
        mask_indices = self._get_static_mask_indices(array_a.shape[:2])
        blended = self._blend_static_arrays(array_a, array_b, mask_indices)
        pygame.surfarray.blit_array(window.screen, blended)

    def _render_gaussian_transition(
        self,
        window: DisplayContext,
        window_a: DisplayContext,
        window_b: DisplayContext,
    ) -> None:
        array_a = pygame.surfarray.array3d(window_a.screen)
        array_b = pygame.surfarray.array3d(window_b.screen)
        mask_values = self._get_gaussian_mask_values(array_a.shape[:2])
        blended = self._blend_gaussian_arrays(array_a, array_b, mask_values)
        pygame.surfarray.blit_array(window.screen, blended)

    def _get_static_mask_indices(self, shape: tuple[int, int]) -> np.ndarray:
        if self._static_mask_indices is None or self._static_mask_shape != shape:
            width, height = shape
            total_pixels = width * height
            rng = np.random.default_rng()
            indices = np.arange(total_pixels, dtype=np.int32)
            rng.shuffle(indices)
            self._static_mask_indices = indices
            self._static_mask_shape = shape
        return self._static_mask_indices

    def _get_gaussian_mask_values(self, shape: tuple[int, int]) -> np.ndarray:
        if self._static_mask_values is None or self._static_mask_shape != shape:
            width, height = shape
            rng = np.random.default_rng()
            noise = rng.random((width, height), dtype=np.float32)
            blurred = self._gaussian_blur(noise, self.provider.gaussian_sigma)
            self._static_mask_values = blurred
            self._static_mask_shape = shape
        return self._static_mask_values

    def _blend_static_arrays(
        self,
        array_a: np.ndarray,
        array_b: np.ndarray,
        mask_indices: np.ndarray,
    ) -> np.ndarray:
        total_pixels = array_a.shape[0] * array_a.shape[1]
        step = min(
            int(self.state.fraction_offset * self.provider.static_mask_steps),
            self.provider.static_mask_steps,
        )
        threshold = int(total_pixels * (step / self.provider.static_mask_steps))
        blended = array_a.copy()
        if threshold <= 0:
            return blended
        flat_a = blended.reshape(-1, 3)
        flat_b = array_b.reshape(-1, 3)
        selected = mask_indices[:threshold]
        flat_a[selected] = flat_b[selected]
        return blended

    def _blend_gaussian_arrays(
        self,
        array_a: np.ndarray,
        array_b: np.ndarray,
        mask_values: np.ndarray,
    ) -> np.ndarray:
        step = min(
            int(self.state.fraction_offset * self.provider.static_mask_steps),
            self.provider.static_mask_steps,
        )
        threshold = step / self.provider.static_mask_steps
        blended = array_a.copy()
        if threshold <= 0:
            return blended
        mask = mask_values <= threshold
        blended[mask] = array_b[mask]
        return blended

    @staticmethod
    def _gaussian_blur(values: np.ndarray, sigma: float) -> np.ndarray:
        radius = max(int(3 * sigma), 1)
        kernel = SlideTransitionRenderer._gaussian_kernel(radius, sigma)
        blurred = SlideTransitionRenderer._convolve_axis(values, kernel, axis=0)
        blurred = SlideTransitionRenderer._convolve_axis(blurred, kernel, axis=1)
        return blurred

    @staticmethod
    def _gaussian_kernel(radius: int, sigma: float) -> np.ndarray:
        axis = np.arange(-radius, radius + 1, dtype=np.float32)
        kernel = np.exp(-(axis ** 2) / (2 * sigma ** 2))
        kernel /= np.sum(kernel)
        return kernel

    @staticmethod
    def _convolve_axis(
        values: np.ndarray, kernel: np.ndarray, *, axis: int
    ) -> np.ndarray:
        pad = len(kernel) // 2
        pad_width = [(0, 0)] * values.ndim
        pad_width[axis] = (pad, pad)
        padded = np.pad(values, pad_width=pad_width, mode="edge")
        output = np.empty_like(values)
        for index in range(values.shape[axis]):
            start = index
            end = index + len(kernel)
            slicer = [slice(None)] * values.ndim
            slicer[axis] = slice(start, end)
            output_slicer = [slice(None)] * values.ndim
            output_slicer[axis] = index
            output[tuple(output_slicer)] = np.tensordot(
                padded[tuple(slicer)], kernel, axes=([axis], [0])
            )
        return output
