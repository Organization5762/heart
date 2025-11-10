from __future__ import annotations

from heart.peripheral.configuration import PeripheralConfiguration
from heart.peripheral.core import Peripheral
from heart.peripheral.core.event_bus import (EventBus,
                                             double_tap_virtual_peripheral)
from heart.peripheral.core.manager import PeripheralManager


class _StubPeripheral(Peripheral):
    def run(self) -> None:  # pragma: no cover - nothing to execute
        pass


class _StubRegistry:
    def __init__(self, configuration: PeripheralConfiguration) -> None:
        self._configuration = configuration

    def get(self, name: str):  # pragma: no cover - simple passthrough
        return (lambda manager: self._configuration) if name == "test" else None


class TestPeripheralManager:
    """Group Peripheral Manager tests so peripheral manager behaviour stays reliable. This preserves confidence in peripheral manager for end-to-end scenarios."""

    def test_peripheral_manager_uses_configured_detectors(self) -> None:
        """Verify that peripheral manager uses configured detectors. This keeps hardware telemetry responsive for interactive experiences."""
        captured: list[str] = []
        sentinel = _StubPeripheral()

        def detector():
            captured.append("detector")
            yield sentinel

        virtual = double_tap_virtual_peripheral(
            "input.event", output_event_type="output.event", name="virtual.test"
        )

        configuration = PeripheralConfiguration(
            detectors=(detector,),
            virtual_peripherals=(virtual,),
        )

        manager = PeripheralManager(
            configuration="test",
            configuration_registry=_StubRegistry(configuration),
        )
        bus = EventBus()
        manager.attach_event_bus(bus)

        manager.detect()

        assert manager.peripherals == (sentinel,)
        assert captured == ["detector"]

        definitions = manager.virtual_peripheral_definitions
        assert set(definitions) == {virtual.name}
        assert definitions[virtual.name] is virtual

        registered = bus.virtual_peripherals.list_definitions().values()
        assert {definition.name for definition in registered} == {virtual.name}
