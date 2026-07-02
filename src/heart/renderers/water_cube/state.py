import colorsys
from dataclasses import dataclass
from functools import lru_cache
from typing import Self, Tuple

import numpy as np
from manyfold import StreamNode

from heart.device import Device
from heart.peripheral.sensor import Acceleration

GRID = 64
SIM_SPEED = 1
SPRING_K = 0.06
NEIGH_K = 0.2
DAMPING = 0.985
DEFAULT_ACCELERATION_AVERAGE = 0.5
DEFAULT_WATER_HUE_DEGREES = 218.0
WATER_SATURATION = 1.0
WATER_VALUE = 1.0


@lru_cache(maxsize=None)
def _grid_offsets(size: int) -> tuple[np.ndarray, np.ndarray]:
    centre = (size - 1) / 2.0
    x_coords, y_coords = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
    return (x_coords - centre, y_coords - centre)


def _target_plane(face_px: int, g: Tuple[float, float, float]) -> np.ndarray:
    """Return a face-sized array of target heights for gravity ``g``."""
    gx, gy, gz = g
    denom = 0.001 + abs(gz)
    slope_x = -gx / denom
    slope_y = gy / denom
    dx, dy = _grid_offsets(face_px)
    return face_px * 0.5 + slope_x * dx + slope_y * dy


@dataclass
class WaterCubeState:
    face_px: int
    heights: np.ndarray
    velocities: np.ndarray
    gvec: Acceleration | None
    acceleration_average: float = DEFAULT_ACCELERATION_AVERAGE
    water_hue_degrees: float = DEFAULT_WATER_HUE_DEGREES

    def gvec_tuple(self):
        accel = self.gvec
        gx = accel.x if accel else 0.0
        gy = -accel.y if accel else 0.0
        gz = accel.z if accel else 1.0
        return (gx, gy, gz)

    def water_rgb(self) -> np.ndarray:
        hue = (self.water_hue_degrees % 360.0) / 360.0
        red, green, blue = colorsys.hsv_to_rgb(hue, WATER_SATURATION, WATER_VALUE)
        return np.array(
            [int(red * 255), int(green * 255), int(blue * 255)],
            dtype=np.uint8,
        )

    def _step(
        self,
        heights: np.ndarray,
        velocities: np.ndarray,
        acceleration: Acceleration | None,
        *,
        acceleration_average: float | None = None,
        water_hue_degrees: float | None = None,
    ) -> "WaterCubeState":
        next_average = (
            self.acceleration_average
            if acceleration_average is None
            else acceleration_average
        )
        next_hue = (
            self.water_hue_degrees if water_hue_degrees is None else water_hue_degrees
        )
        smoothed_acceleration = self._smooth_acceleration(
            acceleration,
            average=next_average,
        )
        gx = smoothed_acceleration.x if smoothed_acceleration else 0.0
        gy = -smoothed_acceleration.y if smoothed_acceleration else 0.0
        gz = smoothed_acceleration.z if smoothed_acceleration else 1.0
        gvec = (gx, gy, gz)
        h_target = _target_plane(self.face_px, gvec)
        diff = heights - h_target
        lap = np.zeros_like(heights)
        lap[1:, :] += heights[:-1, :] - heights[1:, :]
        lap[:-1, :] += heights[1:, :] - heights[:-1, :]
        lap[:, 1:] += heights[:, :-1] - heights[:, 1:]
        lap[:, :-1] += heights[:, 1:] - heights[:, :-1]
        new_velocities = velocities + (-SPRING_K * diff + NEIGH_K * lap) * SIM_SPEED
        new_velocities = new_velocities * DAMPING
        new_heights = heights + new_velocities * SIM_SPEED
        over = new_heights >= self.face_px
        under = new_heights <= 0
        adjusted_heights = new_heights.copy()
        adjusted_heights[over] = self.face_px
        adjusted_heights[under] = 0
        adjusted_velocities = new_velocities.copy()
        adjusted_velocities[np.logical_and(over, adjusted_velocities > 0)] = 0
        adjusted_velocities[np.logical_and(under, adjusted_velocities < 0)] = 0
        return WaterCubeState(
            face_px=self.face_px,
            heights=adjusted_heights,
            velocities=adjusted_velocities,
            gvec=smoothed_acceleration,
            acceleration_average=next_average,
            water_hue_degrees=next_hue,
        )

    def _smooth_acceleration(
        self,
        acceleration: Acceleration | None,
        *,
        average: float,
    ) -> Acceleration | None:
        if acceleration is None or self.gvec is None:
            return acceleration
        follow = max(0.0, min(1.0, average))
        keep = 1.0 - follow
        return Acceleration(
            x=self.gvec.x * keep + acceleration.x * follow,
            y=self.gvec.y * keep + acceleration.y * follow,
            z=self.gvec.z * keep + acceleration.z * follow,
        )

    @classmethod
    def initial_state(cls, device: Device | None = None) -> Self:
        FACE_PX = device.scaled_display_size()[0] // 4
        heights = np.full((FACE_PX, FACE_PX), 0.5 * FACE_PX, dtype=np.float32)
        velocities = np.zeros_like(heights)
        return cls(face_px=FACE_PX, heights=heights, velocities=velocities, gvec=None)

    @classmethod
    def observable(cls, acceleration: StreamNode["Acceleration"]) -> "StreamNode[Self]":
        def update_state(accumulated: Self, a: "Acceleration") -> Self:
            return accumulated._step(
                heights=accumulated.heights,
                velocities=accumulated.velocities,
                acceleration=a,
            )

        return acceleration.scan(update_state)
