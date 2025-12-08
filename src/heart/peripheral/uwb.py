from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import timedelta
from typing import Iterator, List, Self

import numpy as np
import reactivex
from reactivex import operators as ops

from heart.peripheral.core import Peripheral, PeripheralInfo, PeripheralTag

# --- Shared types ------------------------------------------------------------

@dataclass
class BaseStationMeasurement:
    station_id: str
    x: float
    y: float
    z: float
    distance: float  # measured distance to target


@dataclass
class LocalizedTarget:
    """
    One event from the positioning system.

    - (x, y, z): estimated target position
    - stations: the set of base station positions + their measured distances
    """
    x: float
    y: float
    z: float
    stations: List[BaseStationMeasurement]


# --- Position solver helper --------------------------------------------------

def solve_target_position(
    station_positions: list[tuple[float, float, float]],
    distances: list[float],
) -> tuple[float, float, float]:
    """
    Solve for the target's (x, y, z) using multilateration.

    station_positions: list of (xi, yi, zi)
    distances:         list of di (same order as station_positions)

    Requires at least 4 stations; more will be solved with least squares.
    """
    if len(station_positions) < 4:
        raise ValueError("Need at least 4 base stations for 3D fix")

    p = np.array(station_positions, dtype=float)  # shape (N, 3)
    d = np.array(distances, dtype=float)          # shape (N,)

    p0 = p[0]
    d0 = d[0]

    # Build linear system A * [x, y, z]^T = b
    rows = []
    rhs = []
    for i in range(1, len(p)):
        pi = p[i]
        di = d[i]

        # From (x - xi)^2 + (y - yi)^2 + (z - zi)^2 = di^2
        # subtract equation for station 0:
        # 2*(pi - p0)·[x,y,z] = (||pi||^2 - ||p0||^2) + d0^2 - di^2
        rows.append(2.0 * (pi - p0))
        rhs.append(
            (np.dot(pi, pi) - np.dot(p0, p0)) + d0**2 - di**2
        )

    A = np.vstack(rows)       # shape (N-1, 3)
    b = np.array(rhs)         # shape (N-1,)

    # Least-squares solve (works for exactly- or over-determined)
    x_hat, *_ = np.linalg.lstsq(A, b, rcond=None)
    return float(x_hat[0]), float(x_hat[1]), float(x_hat[2])


# --- Fake UWB positioning peripheral ----------------------------------------

class FakeUWBPositioning(Peripheral[LocalizedTarget | None]):
    """
    Fake positioning peripheral:
    - Defines a few fixed base stations in 3D.
    - Simulates a moving target.
    - Computes noisy distances to each base station.
    - Solves for the target's position and emits a LocalizedTarget event.
    """

    # in meters
    BASE_STATIONS: list[tuple[float, float, float]] = [
        (0.0, 0.0, 2.5),
        (5.0, 0.0, 2.5),
        (5.0, 5.0, 2.5),
        (0.0, 5.0, 2.5),
    ]

    @classmethod
    def detect(cls) -> Iterator[Self]:
        yield cls()

    def peripheral_info(self) -> PeripheralInfo:
        return PeripheralInfo(
            id="fake_uwb_positioning",
            tags=[
                PeripheralTag(name="input_variant", variant="uwb_positioning"),
                PeripheralTag(name="input_mode", variant="xyz_multilateration"),
            ],
        )

    def _event_stream(self) -> reactivex.Observable[LocalizedTarget | None]:
        def simulate_sample(n: int) -> LocalizedTarget:
            # "True" target path: a slow circle in the x-y plane with fixed height
            t = n / 20.0  # time-ish index
            true_x = 2.5 + 1.0 * math.cos(t)
            true_y = 2.5 + 1.0 * math.sin(t)
            true_z = 1.0

            true_pos = np.array([true_x, true_y, true_z], dtype=float)

            # Simulate distances with some noise
            distances: list[float] = []
            station_measurements: list[BaseStationMeasurement] = []

            for idx, (sx, sy, sz) in enumerate(self.BASE_STATIONS):
                station_pos = np.array([sx, sy, sz], dtype=float)
                ideal_d = float(np.linalg.norm(true_pos - station_pos))
                noisy_d = ideal_d + random.gauss(0.0, 0.05)

                distances.append(noisy_d)
                station_measurements.append(
                    BaseStationMeasurement(
                        station_id=f"bs_{idx}",
                        x=sx,
                        y=sy,
                        z=sz,
                        distance=noisy_d,
                    )
                )

            # Solve for estimated target position from the noisy distances
            est_x, est_y, est_z = solve_target_position(
                self.BASE_STATIONS, distances
            )

            return LocalizedTarget(
                x=est_x,
                y=est_y,
                z=est_z,
                stations=station_measurements,
            )

        # Emit a new multilateration solution every 500 ms
        return reactivex.interval(timedelta(milliseconds=500)).pipe(
            ops.map(simulate_sample),
        )
