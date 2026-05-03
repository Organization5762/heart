from typing import Any, Iterable

from manyfold import Graph

from heart.peripheral.configuration import PeripheralConfiguration
from heart.peripheral.configuration_loader import PeripheralConfigurationLoader
from heart.peripheral.core import Peripheral
from heart.peripheral.core.input import (AccelerometerController,
                                         AccelerometerDebugProfile,
                                         ExternalSensorHub,
                                         FrameTickController,
                                         GamepadController, InputDebugTap,
                                         KeyboardController,
                                         MandelbrotControlProfile,
                                         NavigationProfile)
from heart.peripheral.core.streams import GraphRouteStream, PeripheralStreams
from heart.peripheral.gamepad import Gamepad
from heart.peripheral.registry import PeripheralConfigurationRegistry
from heart.peripheral.switch import BluetoothSwitch
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class PeripheralManager:
    """Coordinate detection and execution of available peripherals."""

    def __init__(
        self,
        *,
        configuration: str | None = None,
        configuration_registry: PeripheralConfigurationRegistry | None = None,
        configuration_loader: PeripheralConfigurationLoader | None = None,
    ) -> None:
        self._peripherals: list[Peripheral[Any]] = []
        self._graph = Graph()
        self._graph_node_handles: list[Any] = []
        self._started = False
        if configuration_loader and (configuration or configuration_registry):
            raise ValueError(
                "Provide configuration_loader or configuration/configuration_registry, not both."
            )
        self._configuration_loader = (
            configuration_loader
            or PeripheralConfigurationLoader(
                configuration=configuration,
                registry=configuration_registry,
            )
        )
        self._streams = PeripheralStreams(self._graph, self._iter_peripherals)
        self._debug_tap = InputDebugTap()
        self._frame_tick_controller = FrameTickController(self._debug_tap)
        self._keyboard_controller = KeyboardController(self._debug_tap)
        self._gamepad_controller = GamepadController(self, self._debug_tap)
        self._external_sensor_hub = ExternalSensorHub(
            self._debug_tap, graph=self._graph
        )
        self._navigation_profile = NavigationProfile(
            keyboard_controller=self._keyboard_controller,
            gamepad_controller=self._gamepad_controller,
            debug_tap=self._debug_tap,
            switch_stream_factory=self.get_physical_main_switch_subscription,
        )
        self._accelerometer_controller = AccelerometerController(
            manager=self,
            debug_tap=self._debug_tap,
        )
        self._accelerometer_debug_profile = AccelerometerDebugProfile(
            keyboard_controller=self._keyboard_controller,
            frame_tick_controller=self._frame_tick_controller,
            debug_tap=self._debug_tap,
            external_sensor_hub=self._external_sensor_hub,
            graph=self._graph,
        )
        self._mandelbrot_control_profile = MandelbrotControlProfile(
            keyboard_controller=self._keyboard_controller,
            gamepad_controller=self._gamepad_controller,
            debug_tap=self._debug_tap,
        )

    @property
    def peripherals(self) -> tuple[Peripheral[Any], ...]:
        return tuple(self._peripherals)

    @property
    def configuration_loader(self) -> PeripheralConfigurationLoader:
        return self._configuration_loader

    @property
    def configuration_registry(self) -> PeripheralConfigurationRegistry:
        return self._configuration_loader.registry

    @property
    def graph(self) -> Graph:
        return self._graph

    @property
    def graph_node_handles(self) -> tuple[Any, ...]:
        return tuple(self._graph_node_handles)

    def detect(self) -> None:
        configuration = self._ensure_configuration()
        for peripheral in self._iter_detected_peripherals(configuration):
            self._register_peripheral(peripheral)

        for graph_node_factory in configuration.graph_nodes:
            graph_node = graph_node_factory(
                start_immediately=True,
                on_detect=lambda peripheral, _access: self._register_peripheral(
                    peripheral
                ),
            )
            handle = graph_node.install(self._graph)
            self._graph_node_handles.append(handle)
            node_handle = getattr(handle, "node_handle", None)
            if node_handle is not None:
                node_handle.join()

    def register(self, peripheral: Peripheral[Any]) -> None:
        """Manually register ``peripheral`` with the manager."""

        self._register_peripheral(peripheral)

    def _iter_detected_peripherals(
        self,
        configuration: PeripheralConfiguration,
    ) -> Iterable[Peripheral[Any]]:
        for detector in configuration.detectors:
            yield from detector()

    def _ensure_configuration(self) -> PeripheralConfiguration:
        return self._configuration_loader.load()

    def _iter_peripherals(self) -> Iterable[Peripheral[Any]]:
        return tuple(self._peripherals)

    def start(self) -> None:
        if self._started:
            raise ValueError("Manager has already been started")

        self._started = True
        for peripheral in self._peripherals:
            logger.info(f"Attempting to start peripheral '{peripheral}'")
            peripheral.run()

    def stop(self) -> None:
        for handle in reversed(self._graph_node_handles):
            dispose = getattr(handle, "dispose", None)
            if dispose is not None:
                dispose(timeout=1.0)

    def _register_peripheral(self, peripheral: Peripheral[Any]) -> None:
        self._peripherals.append(peripheral)

    def get_main_switch_subscription(self) -> Any:
        return self._streams.main_switch_subscription()

    def get_physical_main_switch_subscription(
        self,
    ) -> Any:
        return self._streams.physical_main_switch_subscription()

    def bluetooth_switch(self) -> BluetoothSwitch | None:
        for peripheral in self._peripherals:
            if isinstance(peripheral, BluetoothSwitch):
                return peripheral
        return None

    def get_gamepad(self) -> Gamepad | None:
        for peripheral in self._peripherals:
            if isinstance(peripheral, Gamepad):
                return peripheral
        return None

    @property
    def game_tick(self) -> GraphRouteStream[Any]:
        return self._streams.game_tick

    @property
    def window(self) -> GraphRouteStream[Any]:
        return self._streams.window

    @property
    def clock(self) -> GraphRouteStream[Any]:
        return self._streams.clock

    @property
    def debug_tap(self) -> InputDebugTap:
        return self._debug_tap

    @property
    def frame_tick_controller(self) -> FrameTickController:
        return self._frame_tick_controller

    @property
    def keyboard_controller(self) -> KeyboardController:
        return self._keyboard_controller

    @property
    def gamepad_controller(self) -> GamepadController:
        return self._gamepad_controller

    @property
    def navigation_profile(self) -> NavigationProfile:
        return self._navigation_profile

    @property
    def external_sensor_hub(self) -> ExternalSensorHub:
        return self._external_sensor_hub

    @property
    def accelerometer_controller(self) -> AccelerometerController:
        return self._accelerometer_controller

    @property
    def accelerometer_debug_profile(self) -> AccelerometerDebugProfile:
        return self._accelerometer_debug_profile

    @property
    def mandelbrot_control_profile(self) -> MandelbrotControlProfile:
        return self._mandelbrot_control_profile
