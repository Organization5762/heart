#!/usr/bin/env python3
"""
This computes a 64x64 height-field that is projected onto the cube's four 64x64 faces.
===================================================

*   Internal grid: 64x64 columns, each storing water height in **pixel
    units** (0-64).
*   Physics: Figure out the equilibrium plane for the current gravity direction, then use spring based physics to move the heights towards that target plane.
    Plus neighbour coupling for ripples.
"""

from __future__ import annotations

import math
import time
from typing import Tuple

import numpy as np
import pygame
from pygame import Surface
from pygame.time import Clock

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.peripheral.manager import PeripheralManager

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
    l = math.hypot(v[0], v[1]) + abs(v[2])
    if l == 0:
        return (0.0, 0.0, 0.0)
    return (v[0] / l, v[1] / l, v[2] / l)


def _target_plane(g: Tuple[float, float, float]) -> np.ndarray:
    """Return GRID×GRID array of target heights for gravity **g**."""
    gx, gy, gz = g
    # avoid blow-up when gz ~ 0 (cube on its side)
    denom = 0.001 + abs(gz)
    slope_x = -gx / denom
    slope_y = -gy / denom

    return INIT_FILL + slope_x * DX + slope_y * DY


class WaterCube(BaseRenderer):
    """Height-field water simulation projected to four LED faces."""

    def __init__(self) -> None:
        self.device_display_mode = DeviceDisplayMode.FULL

        # physics state (float32 for speed on Pi)
        self.h = np.full((GRID, GRID), INIT_FILL, dtype=np.float32)
        self.v = np.zeros_like(self.h)

        # reusable framebuffer (x, y, RGB)
        self._frame = np.zeros((CUBE_PX_W, CUBE_PX_H, 3), np.uint8)

    # ─────────────────────── physics step ────────────────────────────────
    def _step(self, gvec: Tuple[float, float, float]):
        h_target = _target_plane(gvec)

        diff = self.h - h_target

        lap = np.zeros_like(self.h)
        lap[1:, :] += self.h[:-1, :] - self.h[1:, :]
        lap[:-1, :] += self.h[1:, :] - self.h[:-1, :]
        lap[:, 1:] += self.h[:, :-1] - self.h[:, 1:]
        lap[:, :-1] += self.h[:, 1:] - self.h[:, :-1]

        self.v += (-SPRING_K * diff + NEIGH_K * lap) * SIM_SPEED
        self.v *= DAMPING
        self.h += self.v * SIM_SPEED

        # ── boundary handling ──
        over = self.h >= FACE_PX
        under = self.h <= 0
        self.h[over] = FACE_PX
        self.h[under] = 0
        # zero outward velocity at the boundary
        self.v[over & (self.v > 0)] = 0
        self.v[under & (self.v < 0)] = 0

    # ─────────────────────── rendering helpers ───────────────────────────
    def _face_heights(self, face_idx: int) -> np.ndarray:
        """Return 1-D array of GRID heights for cube *face_idx*."""
        if face_idx == 0:  # +X (east)
            return np.flip(self.h[-1, :])  # x = GRID-1, varying y
        if face_idx == 1:  # +Y (north)
            return np.flip(self.h[:, 0])  # y = 0, varying x
        if face_idx == 2:  # −X (west)
            return self.h[0, :]  # x = 0
        return self.h[:, -1]  # −Y (south)

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

    def process(
        self,
        window: Surface,
        clock: Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        # Start timing
        start_time = time.time()

        # --- get gravity ---------------------------------------------------
        accel = peripheral_manager.get_accelerometer().get_acceleration()
        gx = accel.x if accel else 0.0
        gy = accel.y if accel else 0.0
        gz = accel.z if accel else 1.0  # default "down"

        gvec = _norm((gx, gy, gz))
        # --- physics -------------------------------------------------------
        self._step(gvec)

        # --- compose frame -------------------------------------------------
        frame = self._frame
        frame.fill(0)
        for face in range(4):
            heights = self._face_heights(face)
            mask = self._mask_from_heights(heights, gz)
            x0 = face * FACE_PX
            frame[x0 : x0 + FACE_PX, :][mask] = BLUE

        # --- blit to LED surfaces -----------------------------------------
        pygame.surfarray.blit_array(window, frame)

        # Calculate and print frame processing time
        frame_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        print(f"Water cube frame time: {frame_time:.2f} ms")

        # maintain original display rate
        clock.tick_busy_loop(60)
