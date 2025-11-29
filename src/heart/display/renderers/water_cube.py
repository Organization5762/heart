#!/usr/bin/env python3
"""
This computes a 64x64 height-field that is projected onto the cube's four 64x64 faces.
===================================================

*   Internal grid: 64x64 columns, each storing water height in **pixel
    units** (0-64).
*   Physics: Figure out the equilibrium plane for the current gravity direction, then use spring based physics to move the heights towards that target plane.
    Plus neighbour coupling for ripples.
"""

import math
from typing import Tuple

import numpy as np
import pygame
from pygame import Surface
from pygame.time import Clock
from reactivex import Observable

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import StatefulBaseRenderer
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.virtual.water_cube import WaterCubeState

# ───────────────────────── constants & tunables ───────────────────────────────
FACE_PX = 64  # physical LED face resolution (square)
GRID = 64  # internal height-field resolution
SIM_SPEED = 1
SPRING_K = 6.0e-2  # spring to static plane
NEIGH_K = 2.0e-1  # neighbour coupling (ripples)
DAMPING = 0.985  # velocity decay
INIT_FILL = 0.5 * FACE_PX  # half-full cube at rest (pixels)
BLUE = np.array([0, 90, 255], np.uint8)

CUBE_PX_W = FACE_PX * 4  # 256
CUBE_PX_H = FACE_PX  # 64

# grid coordinate helpers
_centre = (GRID - 1) / 2.0
X_COORDS, Y_COORDS = np.meshgrid(np.arange(GRID), np.arange(GRID), indexing="ij")
DX = X_COORDS - _centre
DY = Y_COORDS - _centre


def _norm(v: Tuple[float, float, float]) -> Tuple[float, float, float]:
    length = math.hypot(v[0], v[1]) + abs(v[2])
    if length == 0:
        return (0.0, 0.0, 0.0)
    return (v[0] / length, v[1] / length, v[2] / length)


def _target_plane(g: Tuple[float, float, float]) -> np.ndarray:
    """Return GRID×GRID array of target heights for gravity **g**."""
    gx, gy, gz = g
    # avoid blow-up when gz ~ 0 (cube on its side)
    denom = 0.001 + abs(gz)
    slope_x = -gx / denom
    slope_y = gy / denom

    return INIT_FILL + slope_x * DX + slope_y * DY


class WaterCube(StatefulBaseRenderer[WaterCubeState]):
    """Height-field water simulation projected to four LED faces."""

    def __init__(self) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL

    def state_observable(self,
        peripheral_manager: PeripheralManager,
    ) -> Observable[WaterCubeState]:
        return WaterCubeState.observable(
            peripheral_manager.get_accelerometer_subscription()
        )

    # ─────────────────────── rendering helpers ───────────────────────────
    def _face_heights(self, heights: np.ndarray, face_idx: int) -> np.ndarray:
        """Return 1-D array of GRID heights for cube *face_idx*."""
        if face_idx == 0:  # +X (east)
            return np.flip(heights[-1, :])  # x = GRID-1, varying y
        if face_idx == 1:  # +Y (north)
            return np.flip(heights[:, 0])  # y = 0, varying x
        if face_idx == 2:  # −X (west)
            return heights[0, :]  # x = 0
        return heights[:, -1]  # −Y (south)

    def _mask_from_heights(self, heights: np.ndarray, gz: float) -> np.ndarray:
        """Convert GRID-length *heights* → 64×64 boolean mask."""
        mask = np.zeros((FACE_PX, FACE_PX), bool)
        # map every LED column to a grid column via COL_LUT
        for col_px, grid_col in enumerate(heights):
            h_pix = int(grid_col)
            if h_pix > 0:
                if gz >= 0:
                    # Fill from bottom up when gravity is pointing down
                    mask[col_px, FACE_PX - h_pix :] = True
                else:
                    # Fill from top down when gravity is pointing up
                    mask[col_px, :h_pix] = True
        return mask

    def real_process(
        self,
        window: Surface,
        clock: Clock,
        orientation: Orientation,
    ) -> None:
        gvec = _norm(self.state.gvec_tuple())
        _, _, gz = gvec

        # --- compose frame -------------------------------------------------
        frame = np.zeros((CUBE_PX_W, CUBE_PX_H, 3), dtype=np.uint8)
        for face in range(4):
            face_heights = self._face_heights(self.heights, face)
            mask = self.state._mask_from_heights(face_heights, gz)
            x0 = face * FACE_PX
            face_view = frame[x0 : x0 + FACE_PX, :]
            face_view[mask] = BLUE

        # --- blit to LED surfaces -----------------------------------------
        pygame.surfarray.blit_array(window, frame)

        # maintain original display rate
        clock.tick_busy_loop(60)