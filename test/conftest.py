import os
import pytest

from heart.device import Cube, Device
from heart.environment import GameLoop
from heart.peripheral.manager import PeripheralManager
import numpy as np
from scipy.optimize import curve_fit
from pytest_benchmark.fixture import BenchmarkFixture
import pytest
import functools

class FakeFixtureDevice(Device):
    def individual_display_size(self) -> tuple[int, int]:
        return (64, 64)

@pytest.fixture()
def orientation() -> Cube:
    return Cube.sides()

@pytest.fixture()
def device(orientation) -> Device:
    return FakeFixtureDevice(orientation=orientation)

@pytest.fixture()
def manager() -> PeripheralManager:
    return PeripheralManager()


@pytest.fixture()
def loop(manager, device) -> GameLoop:
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    loop = GameLoop(device=device, peripheral_manager=manager)
    # We just initialize the PyGame screen because peripherals and the fact that we expect, in practice,
    # for this to be a singleton _shouldn't_ be that important for testing
    loop._initialize_screen()
    return loop