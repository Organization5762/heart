import asyncio
import json
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable, Iterable, Iterator, Mapping, Self

import serial
from bleak.backends.device import BLEDevice
from manyfold import (DetectionNode, Graph, Layer, ManagedGraphNode,
                      ManagedGraphNodeHandle, OwnerName, Plane, Schema,
                      StreamFamily, StreamName, TypedRoute, Variant, route)
from manyfold.sensor_io import (BackoffPolicy, ManagedRunLoop,
                                ManagedRunLoopHandle, RetryPolicy, SensorEvent,
                                StopToken, sensor_event_schema)

import heart.utilities.reactive as reactive
from heart.peripheral.bluetooth import UartListener
from heart.peripheral.core import (Peripheral, PeripheralInfo,
                                   PeripheralMessageEnvelope, PeripheralTag)
from heart.peripheral.keyboard import (KeyboardEvent, KeyboardKey,
                                       KeyPressedEvent)
from heart.utilities.env import Configuration, get_device_ports
from heart.utilities.logging import get_logger
from heart.utilities.reactive import operators as ops
from heart.utilities.reactive_threads import (interval_in_background,
                                              pipe_in_background)

logger = get_logger(__name__)
SERIAL_RECONNECT_DELAY_SECONDS = 0.1
BLUETOOTH_EVENT_POLL_DELAY_SECONDS = 0.1
BLUETOOTH_RETRY_DELAY_SECONDS = 5
BLUETOOTH_SLOW_RETRY_DELAY_SECONDS = 30
BLUETOOTH_MAX_RETRY_ATTEMPTS = 5
BLUETOOTH_SWITCH_THREAD_NAME = "peripheral-bluetooth-switch"
BUTTON_PRESS_EVENT = "button.press"
BUTTON_LONG_PRESS_EVENT = "button.long_press"
SWITCH_ROTATION_EVENT = "switch.rotation"
SWITCH_GRAPH_OWNER = OwnerName("heart.switch")
SWITCH_GRAPH_FAMILY = StreamFamily("peripheral")


def switch_state_event_route() -> TypedRoute[SensorEvent]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=SWITCH_GRAPH_OWNER,
        family=SWITCH_GRAPH_FAMILY,
        stream=StreamName("state"),
        variant=Variant.Meta,
        schema=sensor_event_schema("HeartSwitchStateEvent"),
    )


def switch_detection_route() -> TypedRoute[SensorEvent]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=SWITCH_GRAPH_OWNER,
        family=SWITCH_GRAPH_FAMILY,
        stream=StreamName("detected"),
        variant=Variant.Meta,
        schema=sensor_event_schema("HeartSwitchDetectionEvent"),
    )


def switch_exception_schema() -> Schema[BaseException]:
    def encode(exc: BaseException) -> bytes:
        return f"{type(exc).__name__}:{exc}".encode("utf-8")

    def decode(payload: bytes) -> BaseException:
        return RuntimeError(payload.decode("utf-8"))

    return Schema(
        schema_id="PythonException",
        version=1,
        encode=encode,
        decode=decode,
    )


def switch_error_route() -> TypedRoute[BaseException]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=SWITCH_GRAPH_OWNER,
        family=SWITCH_GRAPH_FAMILY,
        stream=StreamName("errors"),
        variant=Variant.Meta,
        schema=switch_exception_schema(),
    )


@dataclass(frozen=True, slots=True)
class SwitchState:
    """Immutable snapshot of ``BaseSwitch`` state values."""

    rotational_value: int
    button_value: int
    long_button_value: int
    rotation_since_last_button_press: int
    rotation_since_last_long_button_press: int

class BaseSwitch(Peripheral[SwitchState]):
    def __init__(
        self,
    ) -> None:
        super().__init__()
        self.rotational_value = 0

        self.button_value = 0
        self.rotation_value_at_last_button_press = self.rotational_value

        self.button_long_press_value = 0
        self.rotation_value_at_last_long_button_press = self.rotational_value

    def _event_stream(
        self
    ) -> reactive.Observable[SwitchState]:
        return pipe_in_background(
            interval_in_background(period=timedelta(milliseconds=10)),
            ops.map(lambda _: self._snapshot()),
            ops.distinct_until_changed(lambda x: x)
        )

    def _snapshot(self) -> SwitchState:
        result = SwitchState(
            rotational_value=self.rotational_value,
            button_value=self.button_value,
            rotation_since_last_button_press=self.rotational_value - self.rotation_value_at_last_button_press,
            long_button_value=self.button_long_press_value,
            rotation_since_last_long_button_press=self.rotational_value - self.rotation_value_at_last_long_button_press,
        )
        return result

    def get_rotation_since_last_long_button_press(self) -> int:
        return self.rotational_value - self.rotation_value_at_last_long_button_press

    @classmethod
    def detection_node(
        cls,
        *,
        detector: Callable[[], Iterable[Peripheral[Any]]] | None = None,
        output_route: TypedRoute[SensorEvent] | None = None,
        state_output_route: TypedRoute[SensorEvent] | None = None,
        state_error_route: TypedRoute[BaseException] | None = None,
        spawn_sources: bool = False,
        on_detect: Any | None = None,
        start_immediately: bool = True,
    ) -> DetectionNode:
        resolved_output_route = output_route or switch_detection_route()
        resolved_state_output_route = state_output_route or switch_state_event_route()

        def mapper(peripheral: "BaseSwitch") -> SensorEvent:
            return SensorEvent(
                event_type="peripheral.switch.detected",
                data={"kind": type(peripheral).__name__},
                observed_at=time.time(),
                identity=peripheral.peripheral_info().to_sensor_identity(),
            )

        def spawn(peripheral: "BaseSwitch", access: Any) -> None:
            if not spawn_sources:
                return
            install_node = getattr(peripheral, "install_node", None)
            if install_node is None:
                return
            access.own(
                install_node(
                    access.graph,
                    output_route=resolved_state_output_route,
                    error_route=state_error_route or switch_error_route(),
                )
            )

        return DetectionNode(
            name="heart-switch-detection",
            detector=detector or cls.detect,
            output_route=resolved_output_route,
            mapper=mapper,
            on_detect=on_detect,
            spawn=spawn,
            error_route=switch_error_route(),
            group="switch-detection",
            start_immediately=start_immediately,
        )

    def update_due_to_data(self, data: Mapping[str, Any]) -> None:
        event_type = data.get("event_type")
        value = data.get("data")
        if event_type == SWITCH_ROTATION_EVENT:
            if value is None:
                logger.debug("Ignoring malformed switch rotation payload: %s", data)
                return
            try:
                self.rotational_value = int(value)
            except (TypeError, ValueError):
                logger.debug("Ignoring malformed switch rotation payload: %s", data)
            return
        if event_type == BUTTON_PRESS_EVENT:
            if value:
                self.button_value += 1
                self.rotation_value_at_last_button_press = self.rotational_value
            return
        if event_type == BUTTON_LONG_PRESS_EVENT:
            if value:
                self.button_long_press_value += 1
                self.rotation_value_at_last_long_button_press = self.rotational_value
            return
        super().update_due_to_data(data)

    def _state_to_sensor_event(self, state: SwitchState) -> SensorEvent:
        return SensorEvent(
            event_type="peripheral.switch.state",
            data={
                "rotational_value": state.rotational_value,
                "button_value": state.button_value,
                "long_button_value": state.long_button_value,
                "rotation_since_last_button_press": (
                    state.rotation_since_last_button_press
                ),
                "rotation_since_last_long_button_press": (
                    state.rotation_since_last_long_button_press
                ),
            },
            observed_at=time.time(),
            identity=self.peripheral_info().to_sensor_identity(),
        )

class FakeSwitch(BaseSwitch):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._navigation_subscription = None

    def _key_press_stream(self, key: int) -> reactive.Observable[KeyboardEvent]:
        def _unwrap(envelope: PeripheralMessageEnvelope[KeyboardEvent]) -> KeyboardEvent:
            return envelope.data

        def _is_pressed(event: KeyboardEvent) -> bool:
            return isinstance(event, KeyPressedEvent)

        result = pipe_in_background(
            KeyboardKey.get(key).observe,
            ops.map(_unwrap),
            ops.filter(_is_pressed),
        )
        return result

    @classmethod
    def detect(cls) -> Iterator[Self]:
        yield cls()

    def peripheral_info(self) -> PeripheralInfo:
        return PeripheralInfo(
            id="fake_switch",
            tags=[
                PeripheralTag(
                    name="input_variant",
                    variant="button",
                    metadata={"version": "v1"}
                ),
                # TODO: Allow the button to change its own tags in some cases
                PeripheralTag(
                    name="mode",
                    variant="main_rotary_button",
                ),
            ]
        )

    def run(self) -> None:
        if (
            Configuration.use_mock_switch()
            or not (Configuration.is_pi() and not Configuration.is_x11_forward())
        ):
            from heart.runtime.game_loop import GameLoop

            loop = GameLoop.get_game_loop()
            if loop is None:
                logger.warning("FakeSwitch requires an active GameLoop for navigation input")
                return

            navigation = loop.peripheral_manager.navigation_profile
            self._navigation_subscription = navigation.subscribe_events(
                on_browse_delta=self._handle_browse,
                on_activate=self._handle_activate,
                on_alternate_activate=self._handle_alternate_activate,
            )
        else:
            logger.warning("Not running FakeSwitch")

    def _handle_alternate_activate(self, _: Any) -> None:
        self.button_long_press_value += 1
        self.rotation_value_at_last_long_button_press = self.rotational_value

    def _handle_activate(self, _: Any) -> None:
        self.button_value += 1
        self.rotation_value_at_last_button_press = self.rotational_value

    def _handle_browse(self, delta: int) -> None:
        self.rotational_value += delta

    def _event_stream(
        self
    ) -> reactive.Observable[SwitchState]:
        if Configuration.is_pi() and not Configuration.is_x11_forward():
            return reactive.empty()
        else:
            result = pipe_in_background(
                interval_in_background(period=timedelta(milliseconds=10)),
                ops.map(lambda _: self._snapshot()),
                ops.distinct_until_changed(lambda x: x),
            )
            return result

class Switch(BaseSwitch):
    def __init__(self, port: str, baudrate: int, *args: Any, **kwargs: Any) -> None:
        self.port = port
        self.baudrate = baudrate
        self._loop_handle: ManagedRunLoopHandle | None = None
        super().__init__(*args, **kwargs)

    @classmethod
    def detect(cls) -> Iterator[Self]:
        for port in get_device_ports("usb-Adafruit_Industries_LLC_Rotary_Trinkey_M0"):
            yield cls(port=port, baudrate=115200)

    def _connect_to_ser(self) -> Any:
        return serial.Serial(self.port, self.baudrate)

    def run(self) -> None:
        if self._loop_handle is not None and self._loop_handle.thread.is_alive():
            return
        loop = ManagedRunLoop(
            body=self._run_serial_loop,
            backoff=BackoffPolicy.fixed(SERIAL_RECONNECT_DELAY_SECONDS),
            on_error=lambda _exc, attempt: logger.exception(
                "Switch serial reader failed; reconnecting (attempt %s).",
                attempt,
            ),
            group="switch",
        )
        self._loop_handle = loop.start_thread(
            name="peripheral-switch",
            daemon=True,
        )

    def stop(self) -> None:
        if self._loop_handle is not None:
            self._loop_handle.stop()

    def _run_serial_loop(self, stop: StopToken) -> None:
        try:
            with self._connect_to_ser() as ser:
                while not stop.is_set():
                    if ser.in_waiting <= 0:
                        stop.wait(SERIAL_RECONNECT_DELAY_SECONDS)
                        continue
                    bus_data = ser.readline().decode("utf-8").rstrip()
                    data = json.loads(bus_data)
                    self.update_due_to_data(data)
        except KeyboardInterrupt:
            stop.set()

    def peripheral_info(self) -> PeripheralInfo:
        return PeripheralInfo(
            id=f"switch:{self.port}",
            tags=[
                PeripheralTag(
                    name="input_variant",
                    variant="button",
                    metadata={"version": "v1"},
                ),
                PeripheralTag(name="mode", variant="main_rotary_button"),
            ],
        )

    def install_node(
        self,
        graph: Graph,
        *,
        output_route: TypedRoute[SensorEvent] | None = None,
        error_route: TypedRoute[BaseException] | None = None,
        retry: RetryPolicy | None = None,
        backoff: BackoffPolicy | None = None,
        start_immediately: bool = True,
    ) -> ManagedGraphNodeHandle:
        resolved_output_route = output_route or switch_state_event_route()

        def _body(stop: StopToken, graph: Graph) -> None:
            try:
                with self._connect_to_ser() as ser:
                    while not stop.is_set():
                        if ser.in_waiting <= 0:
                            stop.wait(SERIAL_RECONNECT_DELAY_SECONDS)
                            continue
                        bus_data = ser.readline().decode("utf-8").rstrip()
                        data = json.loads(bus_data)
                        self.update_due_to_data(data)
                        graph.publish(
                            resolved_output_route,
                            self._state_to_sensor_event(self._snapshot()),
                        )
            except KeyboardInterrupt:
                stop.set()
                return

        return ManagedGraphNode(
            name="heart-switch-state",
            body=_body,
            output_routes=(resolved_output_route,),
            error_route=error_route or switch_error_route(),
            retry=retry or RetryPolicy(max_attempts=1_000_000),
            backoff=backoff or BackoffPolicy.fixed(SERIAL_RECONNECT_DELAY_SECONDS),
            group="switch",
            start_immediately=start_immediately,
        ).install(graph)

class BluetoothSwitch(BaseSwitch):
    def __init__(self, device: BLEDevice, *args: Any, **kwargs: Any) -> None:
        self.listener = UartListener(device=device)
        self.switches = [
            BaseSwitch() for index in range(4)
        ]
        self.connected = False
        self._loop_handle: ManagedRunLoopHandle | None = None
        super().__init__(*args, **kwargs)

    def update_due_to_data(self, data: Mapping[str, Any]) -> None:
        raise NotImplementedError("Haven't figured out how to handle this multi-input case well.  Likely just map it to the observable(s)?")
        producer_raw = data.get("producer_id", 0)
        try:
            producer_id = int(producer_raw)
        except (TypeError, ValueError):
            producer_id = 0

        if not 0 <= producer_id < len(self.switches):
            logger.debug("Ignoring switch payload with invalid producer: %s", data)
            return

        payload = dict(data)
        payload["producer_id"] = producer_id
        self.switches[producer_id].update_due_to_data(payload)

        # Update first producer as if it is the main switch
        if producer_id == 0:
            main_switch = self.switches[0]
            self.rotational_value = main_switch.rotational_value

            self.button_value = main_switch.button_value
            self.rotation_value_at_last_button_press = (
                main_switch.rotation_value_at_last_button_press
            )

            self.button_long_press_value = main_switch.button_long_press_value
            self.rotation_value_at_last_long_button_press = (
                main_switch.rotation_value_at_last_long_button_press
            )

    def switch_zero(self) -> BaseSwitch | None:
        if not self.connected:
            return None
        return self.switches[0]

    def switch_one(self) -> BaseSwitch | None:
        if not self.connected:
            return None
        return self.switches[1]

    def switch_two(self) -> BaseSwitch | None:
        if not self.connected:
            return None
        return self.switches[2]

    def switch_three(self) -> BaseSwitch | None:
        if not self.connected:
            return None
        return self.switches[3]

    @classmethod
    def detect(cls) -> Iterator[Self]:
        devices = asyncio.run(UartListener._discover_devices())
        for device in devices:
            yield cls(device=device)

    def peripheral_info(self) -> PeripheralInfo:
        return PeripheralInfo(
            id=f"bluetooth_switch:{self.listener.device.address}",
            tags=[
                PeripheralTag(
                    name="input_variant",
                    variant="button",
                    metadata={"version": "v1"},
                ),
                PeripheralTag(name="transport", variant="bluetooth"),
                PeripheralTag(name="mode", variant="main_rotary_button"),
            ],
        )

    def _connect_to_ser(self) -> None:
        self.listener.start()

    def run(self) -> None:
        if self._loop_handle is not None and self._loop_handle.thread.is_alive():
            return
        loop = ManagedRunLoop(
            body=self._run_listener_loop,
            backoff=BackoffPolicy(
                initial_delay=BLUETOOTH_RETRY_DELAY_SECONDS,
                multiplier=2.0,
                max_delay=BLUETOOTH_SLOW_RETRY_DELAY_SECONDS,
            ),
            on_error=lambda _exc, attempt: logger.exception(
                "Bluetooth switch listener failed; retrying (attempt %s).",
                attempt,
            ),
            group="bluetooth-switch",
        )
        self._loop_handle = loop.start_thread(
            name=BLUETOOTH_SWITCH_THREAD_NAME,
            daemon=True,
        )

    def stop(self) -> None:
        if self._loop_handle is not None:
            self._loop_handle.stop()
        self.listener.close()

    def _run_listener_loop(self, stop: StopToken) -> None:
        self._connect_to_ser()
        self.connected = True
        try:
            while not stop.is_set():
                for event in self.listener.consume_events():
                    self.update_due_to_data(event)
                stop.wait(BLUETOOTH_EVENT_POLL_DELAY_SECONDS)
        finally:
            self.connected = False
            self.listener.close()

    def install_node(
        self,
        graph: Graph,
        *,
        output_route: TypedRoute[SensorEvent] | None = None,
        error_route: TypedRoute[BaseException] | None = None,
        retry: RetryPolicy | None = None,
        backoff: BackoffPolicy | None = None,
        start_immediately: bool = True,
    ) -> ManagedGraphNodeHandle:
        resolved_output_route = output_route or switch_state_event_route()

        def _body(stop: StopToken, graph: Graph) -> None:
            self._connect_to_ser()
            self.connected = True
            try:
                while not stop.is_set():
                    for event in self.listener.consume_events():
                        self.update_due_to_data(event)
                        graph.publish(
                            resolved_output_route,
                            self._state_to_sensor_event(self._snapshot()),
                        )
                    stop.wait(BLUETOOTH_EVENT_POLL_DELAY_SECONDS)
            finally:
                self.connected = False
                self.listener.close()

        return ManagedGraphNode(
            name="heart-bluetooth-switch-state",
            body=_body,
            output_routes=(resolved_output_route,),
            error_route=error_route or switch_error_route(),
            retry=retry or RetryPolicy(max_attempts=BLUETOOTH_MAX_RETRY_ATTEMPTS),
            backoff=backoff
            or BackoffPolicy(
                initial_delay=BLUETOOTH_RETRY_DELAY_SECONDS,
                multiplier=2.0,
                max_delay=BLUETOOTH_SLOW_RETRY_DELAY_SECONDS,
            ),
            group="bluetooth-switch",
            start_immediately=start_immediately,
        ).install(graph)
