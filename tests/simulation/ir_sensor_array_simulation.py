"""IR sensor array activation-based triangulation helpers.

This module provides a toolbox for reasoning about how the IR sensor array
responds to different activation patterns.  Rather than simulating precise
speed-of-light timing, the helpers focus on which sensors report a hit and how
that constrains the direction of the incoming signal.  For each scenario we
extract the sensor positions, determine a best-fit line through the activated
sensors, and compute a representative viewing direction.

The utilities live under :mod:`tests` so that engineers can quickly iterate on
triangulation heuristics without impacting the production firmware images.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np

from heart.peripheral.ir_sensor_array import radial_layout
from heart.utilities.logging import get_logger

LOGGER = get_logger(__name__)


@dataclass(slots=True)
class IRArrayScenario:
    """Description of a single triangulation experiment."""

    name: str
    active_sensors: Sequence[int]
    expected_direction: Sequence[float] | None = None
    sensor_positions: Sequence[Sequence[float]] | None = None


@dataclass(slots=True)
class SimulationResult:
    """Holds derived geometry for an activation scenario."""

    scenario: IRArrayScenario
    active_indices: tuple[int, ...]
    active_positions: np.ndarray
    line_point: np.ndarray
    line_direction: np.ndarray
    view_direction: np.ndarray
    angular_error_deg: float | None

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable representation."""

        payload: dict[str, object] = {
            "scenario": self.scenario.name,
            "active_indices": list(self.active_indices),
            "active_positions": self.active_positions.tolist(),
            "line_point": self.line_point.tolist(),
            "line_direction": self.line_direction.tolist(),
            "view_direction": self.view_direction.tolist(),
        }
        if self.angular_error_deg is not None:
            payload["angular_error_deg"] = self.angular_error_deg
        return payload


def simulate_activation_geometry(
    scenario: IRArrayScenario,
) -> SimulationResult:
    """Derive line and direction estimates for ``scenario``."""

    sensor_positions = (
        np.asarray(scenario.sensor_positions, dtype=float)
        if scenario.sensor_positions is not None
        else np.asarray(radial_layout(), dtype=float)
    )
    if sensor_positions.ndim != 2 or sensor_positions.shape[1] != 3:
        msg = "sensor_positions must be an (N, 3) array"
        raise ValueError(msg)

    active_indices = _unique_indices(scenario.active_sensors)
    active_positions = sensor_positions[np.array(active_indices, dtype=int)]

    line_point, line_direction = _fit_line(active_positions)
    view_direction = _normalize(active_positions.mean(axis=0))

    angular_error = None
    if scenario.expected_direction is not None:
        expected = _normalize(np.asarray(scenario.expected_direction, dtype=float))
        cos_theta = float(np.clip(np.dot(expected, view_direction), -1.0, 1.0))
        angular_error = math.degrees(math.acos(cos_theta))

    return SimulationResult(
        scenario=scenario,
        active_indices=active_indices,
        active_positions=active_positions,
        line_point=line_point,
        line_direction=line_direction,
        view_direction=view_direction,
        angular_error_deg=angular_error,
    )


def run_scenarios(scenarios: Iterable[IRArrayScenario]) -> list[SimulationResult]:
    """Run the simulator for every scenario and return the results."""

    return [simulate_activation_geometry(scenario) for scenario in scenarios]


def _fit_line(active_positions: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if active_positions.size == 0:
        msg = "At least one sensor must be active"
        raise ValueError(msg)

    if len(active_positions) == 1:
        point = active_positions[0]
        return point, _normalize(point)

    centroid = active_positions.mean(axis=0)
    centered = active_positions - centroid
    covariance = centered.T @ centered
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    principal = eigenvectors[:, int(np.argmax(eigenvalues))]
    direction = _normalize(principal)

    # Ensure the direction points roughly away from the origin so that
    # the "forward" assumption lines up with the sensor layout.
    if np.dot(direction, centroid) < 0:
        direction = -direction

    return centroid, direction


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm == 0.0:
        msg = "Cannot normalise the zero vector"
        raise ValueError(msg)
    return vector / norm


def _unique_indices(indices: Sequence[int]) -> tuple[int, ...]:
    if not indices:
        msg = "active_sensors must contain at least one index"
        raise ValueError(msg)
    seen: set[int] = set()
    unique: list[int] = []
    for index in indices:
        if index in seen:
            continue
        if not isinstance(index, int):
            msg = "Sensor indices must be integers"
            raise TypeError(msg)
        seen.add(index)
        unique.append(index)
    return tuple(unique)


def _format_vector(vector: Sequence[float]) -> str:
    return ", ".join(f"{component: .4f}" for component in vector)


def main() -> None:
    """Run a demonstration simulation and print a summary table."""

    scenarios = [
        IRArrayScenario(name="Single-0", active_sensors=(0,)),
        IRArrayScenario(name="Opposite", active_sensors=(0, 2)),
        IRArrayScenario(name="Adjacent", active_sensors=(0, 1)),
        IRArrayScenario(
            name="All", active_sensors=(0, 1, 2, 3), expected_direction=(0.0, 0.0, 1.0)
        ),
    ]
    results = run_scenarios(scenarios)
    header = (
        f"{'Scenario':<12} | {'Active':<12} | {'View direction':<36} | "
        f"{'Line point':<36} | {'Line dir.':<36} | Error (deg)"
    )
    divider = "-" * len(header)
    LOGGER.info(header)
    LOGGER.info(divider)
    for result in results:
        error = f"{result.angular_error_deg:10.4f}" if result.angular_error_deg is not None else "    --    "
        LOGGER.info(
            f"{result.scenario.name:<12} | "
            f"{list(result.active_indices)!s:<12} | "
            f"{_format_vector(result.view_direction):<36} | "
            f"{_format_vector(result.line_point):<36} | "
            f"{_format_vector(result.line_direction):<36} | "
            f"{error}"
        )


if __name__ == "__main__":  # pragma: no cover - manual simulation hook
    main()
