"""Simulation utilities for the IR sensor array peripheral."""

from .ir_sensor_array_simulation import (IRArrayScenario, SimulationResult,
                                         run_scenarios,
                                         simulate_activation_geometry)

__all__ = [
    "IRArrayScenario",
    "SimulationResult",
    "simulate_activation_geometry",
    "run_scenarios",
]
