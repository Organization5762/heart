from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pygame

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.runtime.display_context import DisplayContext
from heart.utilities.color_conversion import (convert_hsv_to_rgb,
                                              convert_rgb_to_hsv)

SATURATION_STEP = 0.05
SATURATION_MIN = 0.0
SATURATION_MAX = 5.0
HUE_STEP = 0.03
EDGE_THRESHOLD_DEFAULT = 1
EDGE_THRESHOLD_STEP = 0.10
EDGE_BACKGROUND_DIM = 0.75
EDGE_GAMMA = 0.5


@dataclass
class PostProcessorState:
    peripheral_manager: PeripheralManager


def _get_image_view(surface: pygame.Surface) -> tuple[np.ndarray, np.ndarray]:
    pixels = pygame.surfarray.pixels3d(surface)
    image = pixels.swapaxes(0, 1)
    return image, pixels


class BasePostProcessor(StatefulBaseRenderer[PostProcessorState]):
    def __init__(self) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL

    def _create_initial_state(
        self,
        window: DisplayContext,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> PostProcessorState:
        return PostProcessorState(peripheral_manager=peripheral_manager)


class SaturationPostProcessor(BasePostProcessor):
    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        bluetooth = self.state.peripheral_manager.bluetooth_switch()
        if bluetooth is None:
            return
        if (switch_one := bluetooth.switch_one()) is None:
            return
        rotation_delta = switch_one.get_rotation_since_last_long_button_press()
        if rotation_delta == 0:
            return

        factor = 1.0 + SATURATION_STEP * rotation_delta
        factor = max(SATURATION_MIN, min(SATURATION_MAX, factor))

        image, pixels = _get_image_view(window.screen)
        img = image.astype(np.float32)
        lum = (
            0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]
        )[..., None]
        img_sat = lum + factor * (img - lum)
        image[:] = np.clip(img_sat, 0, 255).astype(np.uint8)
        del pixels


class HueShiftPostProcessor(BasePostProcessor):
    def __init__(self) -> None:
        super().__init__()
        self._tmp_float: np.ndarray | None = None

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        bluetooth = self.state.peripheral_manager.bluetooth_switch()
        if bluetooth is None:
            return
        hue_switch = bluetooth.switch_two()
        if hue_switch is None:
            return
        delta = hue_switch.get_rotation_since_last_long_button_press()
        if delta == 0:
            return

        image, pixels = _get_image_view(window.screen)
        if self._tmp_float is None or self._tmp_float.shape != image.shape:
            self._tmp_float = np.empty_like(image, dtype=np.float32)

        hue_delta = (delta * HUE_STEP) % 1.0
        hsv = convert_rgb_to_hsv(image)
        self._tmp_float[:] = hsv
        self._tmp_float[..., 0] = (
            (self._tmp_float[..., 0] / 179.0 + hue_delta) % 1.0 * 179.0
        )
        image[:] = convert_hsv_to_rgb(self._tmp_float.astype(np.uint8))
        del pixels


class EdgePostProcessor(BasePostProcessor):
    def __init__(self) -> None:
        super().__init__()
        self.edge_thresh = EDGE_THRESHOLD_DEFAULT

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        bluetooth = self.state.peripheral_manager.bluetooth_switch()
        if bluetooth is None:
            return
        edge_switch = bluetooth.switch_three()
        if edge_switch is None:
            return
        delta = edge_switch.get_rotation_since_last_long_button_press()
        if delta == 0:
            return

        self.edge_thresh = int(
            np.clip(
                self.edge_thresh * (1.0 + EDGE_THRESHOLD_STEP * delta),
                1,
                255,
            )
        )

        image, pixels = _get_image_view(window.screen)
        lum = (
            0.299 * image[..., 0]
            + 0.587 * image[..., 1]
            + 0.114 * image[..., 2]
        ).astype(np.int16)

        gx = np.abs(np.roll(lum, -1, 1) - np.roll(lum, 1, 1))
        gy = np.abs(np.roll(lum, -1, 0) - np.roll(lum, 1, 0))
        edge_mag = gx + gy

        denom = max(1, 255 - self.edge_thresh)
        alpha = np.clip(
            (edge_mag.astype(np.float32) - self.edge_thresh) / denom,
            0.0,
            1.0,
        )
        alpha **= EDGE_GAMMA
        alpha = alpha[..., None]

        base = image.astype(np.float32) * EDGE_BACKGROUND_DIM
        edges = alpha * 255.0
        out = np.clip(base + edges, 0, 255)
        image[:] = out.astype(np.uint8)
        del pixels


class NullPostProcessor(BasePostProcessor):
    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        return
