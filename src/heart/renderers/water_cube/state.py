from dataclasses import dataclass
from typing import Self, Tuple

import numpy as np
from reactivex import operators as ops
from reactivex.observable import Observable

from heart.peripheral.sensor import Acceleration

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


def _target_plane(g: Tuple[float, float, float]) -> np.ndarray:
    """Return GRID×GRID array of target heights for gravity **g**."""
    gx, gy, gz = g
    # avoid blow-up when gz ~ 0 (cube on its side)
    denom = 0.001 + abs(gz)
    slope_x = -gx / denom
    slope_y = gy / denom

    return INIT_FILL + slope_x * DX + slope_y * DY


@dataclass
class WaterCubeState:
    heights: np.ndarray
    velocities: np.ndarray
    gvec: Acceleration | None

    def gvec_tuple(self):
        accel = self.gvec
        gx = accel.x if accel else 0.0
        gy = -accel.y if accel else 0.0
        gz = accel.z if accel else 1.0  # default "down"
        return (gx, gy, gz)

    def _step(
        self,
        heights: np.ndarray,
        velocities: np.ndarray,
        acceleration: Acceleration
    ) -> "WaterCubeState":
        gx = acceleration.x if acceleration else 0.0
        gy = -acceleration.y if acceleration else 0.0
        gz = acceleration.z if acceleration else 1.0  # default "down"
        gvec = (gx, gy, gz)
        h_target = _target_plane(gvec)

        diff = heights - h_target

        lap = np.zeros_like(heights)
        lap[1:, :] += heights[:-1, :] - heights[1:, :]
        lap[:-1, :] += heights[1:, :] - heights[:-1, :]
        lap[:, 1:] += heights[:, :-1] - heights[:, 1:]
        lap[:, :-1] += heights[:, 1:] - heights[:, :-1]

        new_velocities = velocities + (-SPRING_K * diff + NEIGH_K * lap) * SIM_SPEED
        new_velocities = new_velocities * DAMPING
        new_heights = heights + new_velocities * SIM_SPEED

        over = new_heights >= FACE_PX
        under = new_heights <= 0

        adjusted_heights = new_heights.copy()
        adjusted_heights[over] = FACE_PX
        adjusted_heights[under] = 0

        adjusted_velocities = new_velocities.copy()
        adjusted_velocities[np.logical_and(over, adjusted_velocities > 0)] = 0
        adjusted_velocities[np.logical_and(under, adjusted_velocities < 0)] = 0


        # TODO:
        # This is a good example of a state update that would benefit from itself being a virtual peripheral imo? Trying to think this one through
        # Ok with this like this I think we have a path to just registering this as a callback that depends on gvec changing?
        return WaterCubeState(
            heights=adjusted_heights,
            velocities=adjusted_velocities,
            gvec=acceleration,
        )

    @classmethod
    def initial_state(cls) -> Self:
        heights = np.full((64, 64), INIT_FILL, dtype=np.float32)
        velocities = np.zeros_like(heights)
        return cls(
            heights=heights,
            velocities=velocities,
            gvec=None
        )

    @classmethod
    def observable(
        cls,
        acceleration: Observable["Acceleration"],
    ) -> "Observable[Self]":
        initial_state = cls.initial_state()

        def update_state(
            accumulated: Self,
            a: "Acceleration",
        ) -> Self:
            # Advance the simulation one step using the new acceleration
            return accumulated._step(
                heights=accumulated.heights,
                velocities=accumulated.velocities,
                acceleration=a,
            )

        return acceleration.pipe(
            ops.scan(update_state, seed=initial_state),
            ops.start_with(initial_state),
            ops.share(),
        )
