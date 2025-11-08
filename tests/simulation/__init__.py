"""Simulation utilities for the IR sensor array peripheral."""

from . import ir_sensor_array_simulation as _ir_sensor_array_simulation

IRArrayScenario = _ir_sensor_array_simulation.IRArrayScenario
SimulationResult = _ir_sensor_array_simulation.SimulationResult
run_scenarios = _ir_sensor_array_simulation.run_scenarios
simulate_activation_geometry = (
    _ir_sensor_array_simulation.simulate_activation_geometry
)

del _ir_sensor_array_simulation
