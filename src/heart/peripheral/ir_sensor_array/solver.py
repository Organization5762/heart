"""Multilateration solver for IR burst positioning."""

from __future__ import annotations

import math
from typing import Any, Callable, Sequence, cast

import numpy as np

from heart.utilities.logging import get_logger
from heart.utilities.optional_imports import optional_import_attribute

from .constants import SPEED_OF_LIGHT

LeastSquaresCallable = Callable[..., Any]

logger = get_logger(__name__)

DEFAULT_SOLVER_METHOD = "trf"
DEFAULT_MAX_ITERATIONS = 12
DEFAULT_CONVERGENCE_THRESHOLD = 1e-6
DEFAULT_USE_JACOBIAN = True

_least_squares = cast(
    LeastSquaresCallable | None,
    optional_import_attribute("scipy.optimize", "least_squares", logger=logger),
)

if _least_squares is None:

    def least_squares(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("scipy.optimize.least_squares is not available")

else:
    least_squares = _least_squares


class MultilaterationSolver:
    """Estimate the origin of an IR burst using time-difference-of-arrival."""

    def __init__(
        self,
        sensor_positions: Sequence[Sequence[float]],
        *,
        propagation_speed: float = SPEED_OF_LIGHT,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        convergence_threshold: float = DEFAULT_CONVERGENCE_THRESHOLD,
        solver_method: str = DEFAULT_SOLVER_METHOD,
        use_jacobian: bool = DEFAULT_USE_JACOBIAN,
    ) -> None:
        self.sensor_positions = np.asarray(sensor_positions, dtype=float)
        if self.sensor_positions.ndim != 2 or self.sensor_positions.shape[1] != 3:
            msg = "sensor_positions must be an (N,3) array"
            raise ValueError(msg)
        if self.sensor_positions.shape[0] < 3:
            msg = "At least three sensors are required"
            raise ValueError(msg)
        self.propagation_speed = float(propagation_speed)
        self.max_iterations = max_iterations
        self.convergence_threshold = convergence_threshold
        self.solver_method = solver_method
        self.use_jacobian = use_jacobian

    # ------------------------------------------------------------------
    def solve(self, arrival_times: Sequence[float]) -> tuple[np.ndarray, float, float]:
        """Return ``(position, confidence, rmse)`` for ``arrival_times``."""

        times = np.asarray(arrival_times, dtype=float)
        if times.shape[0] != self.sensor_positions.shape[0]:
            msg = "arrival_times length must match number of sensors"
            raise ValueError(msg)

        point = np.mean(self.sensor_positions, axis=0)
        emission_time = float(np.min(times)) - np.linalg.norm(
            point - self.sensor_positions[0]
        ) / self.propagation_speed

        def objective(vector: np.ndarray) -> np.ndarray:
            candidate_point = vector[:3]
            candidate_emission = vector[3]
            deltas = candidate_point - self.sensor_positions
            distances = np.linalg.norm(deltas, axis=1)
            residuals = distances - self.propagation_speed * (times - candidate_emission)
            return np.asarray(residuals, dtype=float)

        def jacobian(vector: np.ndarray) -> np.ndarray:
            candidate_point = vector[:3]
            deltas = candidate_point - self.sensor_positions
            distances = np.linalg.norm(deltas, axis=1)
            jac = np.zeros((distances.shape[0], 4), dtype=float)
            with np.errstate(divide="ignore", invalid="ignore"):
                jac[:, :3] = np.divide(
                    deltas,
                    distances[:, None],
                    out=np.zeros_like(deltas),
                    where=distances[:, None] != 0.0,
                )
            jac[:, 3] = self.propagation_speed
            return jac

        start = np.concatenate([point, [emission_time]])
        least_squares_kwargs = {
            "method": self.solver_method,
            "max_nfev": self.max_iterations * 100,
            "xtol": self.convergence_threshold,
            "ftol": self.convergence_threshold**2,
            "gtol": self.convergence_threshold,
        }
        if self.use_jacobian:
            least_squares_kwargs["jac"] = jacobian
        result = least_squares(objective, start, **least_squares_kwargs)
        if not result.success:
            raise ValueError(f"Solver failed to converge: {result.message}")

        point = result.x[:3]
        emission_time = result.x[3]
        final_residuals = objective(result.x)

        rmse = float(math.sqrt(np.mean(np.square(final_residuals))))
        confidence = float(1.0 / (1.0 + rmse * self.propagation_speed))
        return point, confidence, rmse
