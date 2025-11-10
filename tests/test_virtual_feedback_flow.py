from __future__ import annotations

import os
from collections.abc import Mapping

import pygame
from PIL import Image

from heart.device.single_led import SingleLEDDevice
from heart.environment import GameLoop
from heart.peripheral.average_color_led import AverageColorLED
from heart.peripheral.core import Input, Peripheral
from heart.peripheral.core.event_bus import (VirtualPeripheralContext,
                                             VirtualPeripheralDefinition,
                                             _VirtualPeripheral)
from heart.peripheral.core.manager import PeripheralManager
from tests.conftest import FakeFixtureDevice


class _StaticScalarPeripheral(Peripheral):
    """Utility peripheral that pushes scalar samples on demand."""

    def __init__(self, event_type: str) -> None:
        super().__init__()
        self._event_type = event_type

    def push(self, value: float) -> None:
        self.emit_event(self._event_type, {"value": value})

    def run(self) -> None:  # pragma: no cover - passive test helper
        return None


class _MetricFusionVirtualPeripheral(_VirtualPeripheral):
    """Combine the latest readings from two sensor streams."""

    def __init__(
        self,
        context: VirtualPeripheralContext,
        *,
        event_types: tuple[str, str],
        output_event: str,
    ) -> None:
        super().__init__(context)
        self._event_types = event_types
        self._output_event = output_event
        self._latest: dict[str, float] = {}

    def handle(self, event: Input) -> None:
        if event.event_type not in self._event_types:
            return
        payload = event.data
        if not isinstance(payload, Mapping) or "value" not in payload:
            return
        try:
            value = float(payload["value"])
        except (TypeError, ValueError):
            return
        self._latest[event.event_type] = value
        if len(self._latest) < len(self._event_types):
            return
        values = [self._latest.get(name) for name in self._event_types]
        if any(sample is None for sample in values):
            return
        spread = max(values) - min(values)
        mean = sum(values) / len(values)
        self._context.emit(
            self._output_event,
            {"metrics": {"mean": mean, "spread": spread}},
        )


def _fused_metrics_definition(
    event_types: tuple[str, str],
    output_event: str,
) -> VirtualPeripheralDefinition:
    return VirtualPeripheralDefinition(
        name="tests.metric_fusion",
        event_types=event_types,
        factory=lambda context: _MetricFusionVirtualPeripheral(
            context,
            event_types=event_types,
            output_event=output_event,
        ),
    )


def test_virtual_feedback_flow(orientation) -> None:
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    previous_bus_flag = os.environ.get("ENABLE_INPUT_EVENT_BUS")
    os.environ["ENABLE_INPUT_EVENT_BUS"] = "1"

    try:
        sensor_events = ("tests.sensor.alpha", "tests.sensor.beta")
        fused_event = "tests.virtual.metrics"

        primary_manager = PeripheralManager()
        primary_loop = GameLoop(
            device=FakeFixtureDevice(orientation=orientation),
            peripheral_manager=primary_manager,
        )
        primary_loop._initialize_screen()

        feedback_manager = PeripheralManager()
        feedback_loop = GameLoop(
            device=FakeFixtureDevice(orientation=orientation),
            peripheral_manager=feedback_manager,
            event_bus=primary_loop.event_bus,
        )
        feedback_loop._initialize_screen()

        sensors = [_StaticScalarPeripheral(event) for event in sensor_events]
        for sensor in sensors:
            primary_manager.register(sensor)

        definition = _fused_metrics_definition(sensor_events, fused_event)
        primary_loop.event_bus.virtual_peripherals.register(definition)

        single_led = SingleLEDDevice()
        mirror = AverageColorLED(
            device=single_led,
            source_display=primary_loop.display_peripheral,
        )
        feedback_manager.register(mirror)

        for index, sensor in enumerate(sensors):
            sensor.push(0.25 + 0.5 * index)

        latest_metrics = primary_loop.event_bus.state_store.get_latest(fused_event)
        assert latest_metrics is not None
        payload = latest_metrics.data
        assert isinstance(payload, Mapping)
        metrics = payload.get("metrics")
        assert isinstance(metrics, Mapping)
        mean = float(metrics["mean"])
        spread = float(metrics["spread"])

        colour = (
            int(round(mean * 255)),
            int(round(spread * 255)),
            int(round((1.0 - mean) * 255)),
        )
        image = Image.new("RGB", primary_loop.device.full_display_size(), colour)
        primary_loop.display_peripheral.publish_image(image)

        assert feedback_manager.event_bus is primary_loop.event_bus
        assert feedback_loop.event_bus is primary_loop.event_bus
        assert single_led.last_color == colour
    finally:
        if previous_bus_flag is None:
            os.environ.pop("ENABLE_INPUT_EVENT_BUS", None)
        else:
            os.environ["ENABLE_INPUT_EVENT_BUS"] = previous_bus_flag
        pygame.quit()
