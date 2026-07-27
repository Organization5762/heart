from __future__ import annotations

from typing import cast

import pytest

from heart.world import (
    ActiveMode,
    World,
    WorldDevice,
    WorldDimensions,
    WorldPosition,
)


class TestWorld:
    def test_registers_devices_and_selects_a_local_mode(self) -> None:
        world = World()

        assert world.put_device(_device())
        assert world.select_mode(_active_mode())

        snapshot = world.snapshot()
        assert snapshot.revision == 2
        assert snapshot.devices == (_device(),)
        assert snapshot.active_mode == _active_mode()
        assert world.device("totem3") == _device()

    def test_equivalent_updates_do_not_advance_revision(self) -> None:
        world = World()
        world.put_device(_device())
        world.select_mode(_active_mode())

        assert not world.put_device(_device())
        assert not world.select_mode(_active_mode())
        assert world.revision == 2

    def test_rejects_mode_ownership_by_an_unknown_device(self) -> None:
        world = World()
        before = world.snapshot()

        with pytest.raises(ValueError, match="not registered"):
            world.select_mode(_active_mode())

        assert world.snapshot() == before

    def test_validates_device_dimensions_and_capabilities(self) -> None:
        invalid_dimensions = WorldDevice(
            id="totem3",
            position=WorldPosition(0.0, 0.0, 0.0),
            dimensions=WorldDimensions(0.0, 2.0, 0.5),
        )
        duplicate_capabilities = WorldDevice(
            id="totem3",
            position=WorldPosition(0.0, 0.0, 0.0),
            dimensions=WorldDimensions(0.5, 2.0, 0.5),
            capabilities=("matrix", "matrix"),
        )
        world = World()
        before = world.snapshot()

        with pytest.raises(ValueError, match="greater than zero"):
            world.put_device(invalid_dimensions)
        with pytest.raises(ValueError, match="must be unique"):
            world.put_device(duplicate_capabilities)

        assert world.snapshot() == before

    def test_rejects_mutable_nested_values_and_ambiguous_ids(self) -> None:
        world = World()
        mutable_capabilities = WorldDevice(
            id="totem3",
            position=WorldPosition(0.0, 0.0, 0.0),
            dimensions=WorldDimensions(0.5, 2.0, 0.5),
            capabilities=cast(tuple[str, ...], ["hub75"]),
        )
        invalid_position = WorldDevice(
            id="totem3",
            position=cast(WorldPosition, object()),
            dimensions=WorldDimensions(0.5, 2.0, 0.5),
        )
        spaced_id = WorldDevice(
            id=" totem3 ",
            position=WorldPosition(0.0, 0.0, 0.0),
            dimensions=WorldDimensions(0.5, 2.0, 0.5),
        )
        before = world.snapshot()

        with pytest.raises(TypeError, match="capabilities must be a tuple"):
            world.put_device(mutable_capabilities)
        with pytest.raises(TypeError, match="position must be a WorldPosition"):
            world.put_device(invalid_position)
        with pytest.raises(ValueError, match="leading or trailing whitespace"):
            world.put_device(spaced_id)

        assert world.snapshot() == before

    def test_bounds_registered_device_memory(self) -> None:
        world = World(max_devices=1)
        world.put_device(_device())
        second = WorldDevice(
            id="totem4",
            position=WorldPosition(1.0, 0.0, 0.0),
            dimensions=WorldDimensions(0.5, 2.0, 0.5),
        )
        before = world.snapshot()

        with pytest.raises(ValueError, match="device limit 1"):
            world.put_device(second)

        assert world.snapshot() == before

    def test_replaces_an_existing_device_at_capacity(self) -> None:
        world = World(max_devices=1)
        world.put_device(_device())
        replacement = WorldDevice(
            id="totem3",
            position=WorldPosition(1.0, 0.0, 0.0),
            dimensions=WorldDimensions(0.5, 2.0, 0.5),
            capabilities=("hub75",),
        )

        assert world.put_device(replacement)
        assert world.snapshot().devices == (replacement,)
        assert world.revision == 2

def _device() -> WorldDevice:
    return WorldDevice(
        id="totem3",
        position=WorldPosition(0.0, 0.0, 0.0),
        dimensions=WorldDimensions(0.5, 2.0, 0.5),
        capabilities=("hub75", "gamepad"),
    )


def _active_mode() -> ActiveMode:
    return ActiveMode(
        mode_id="mandelbulb",
        configuration_id="lib-2026",
        owner_device_id="totem3",
    )
