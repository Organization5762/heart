import json
import logging
import random
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Iterator, Mapping, Self, cast

import manyfold.rx as reactivex
import serial
from manyfold import (DetectionNode, Graph, Layer, ManagedGraphNode,
                      ManagedGraphNodeHandle, OwnerName, Plane, Schema,
                      StreamFamily, StreamName, TypedRoute, Variant, route)
from manyfold.rx import operators as ops
from manyfold.sensor_io import (BackoffPolicy, ManagedRunLoop,
                                ManagedRunLoopHandle, RetryPolicy, SensorEvent,
                                StopToken, sensor_event_schema)

from heart.peripheral.core import Peripheral, PeripheralInfo, PeripheralTag
from heart.peripheral.input_payloads.motion import AccelerometerVector
from heart.utilities.env import get_device_ports
from heart.utilities.logging import get_logger
from heart.utilities.logging_control import get_logging_controller
from heart.utilities.reactivex_threads import (interval_in_background,
                                               pipe_in_background)

logger = get_logger(__name__)
RECONNECT_DELAY_SECONDS = 1.0
ACCELEROMETER_THREAD_NAME = "peripheral-accelerometer"
ACCELEROMETER_GRAPH_OWNER = OwnerName("heart.accelerometer")
ACCELEROMETER_GRAPH_FAMILY = StreamFamily("peripheral")


def accelerometer_vector_event_route() -> TypedRoute[SensorEvent]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=ACCELEROMETER_GRAPH_OWNER,
        family=ACCELEROMETER_GRAPH_FAMILY,
        stream=StreamName("vectors"),
        variant=Variant.Meta,
        schema=sensor_event_schema("HeartAccelerometerVectorEvent"),
    )


def accelerometer_detection_route() -> TypedRoute[SensorEvent]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=ACCELEROMETER_GRAPH_OWNER,
        family=ACCELEROMETER_GRAPH_FAMILY,
        stream=StreamName("detected"),
        variant=Variant.Meta,
        schema=sensor_event_schema("HeartAccelerometerDetectionEvent"),
    )


def accelerometer_exception_schema() -> Schema[BaseException]:
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


def accelerometer_error_route() -> TypedRoute[BaseException]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=ACCELEROMETER_GRAPH_OWNER,
        family=ACCELEROMETER_GRAPH_FAMILY,
        stream=StreamName("errors"),
        variant=Variant.Meta,
        schema=accelerometer_exception_schema(),
    )


@dataclass
class Acceleration:
    x: float
    y: float
    z: float


class Accelerometer(Peripheral[Acceleration | None]):
    def __init__(
        self,
        port: str,
        baudrate: int,
    ) -> None:
        super().__init__()
        self.acceleration_value: dict[str, float] | None = None
        self.port = port
        self.baudrate = baudrate
        self._log_controller = get_logging_controller()
        self._messages_received = 0
        self._decode_failures = 0
        self._loop_handle: ManagedRunLoopHandle | None = None

    def _event_stream(
        self
    ) -> reactivex.Observable[Acceleration | None]:
        return pipe_in_background(
            interval_in_background(period=timedelta(milliseconds=10)),

            ops.map(lambda _: self.get_acceleration()),
            ops.distinct_until_changed(lambda x: x)
        )

    @classmethod
    def detect(cls) -> Iterator[Self]:
        for port in get_device_ports("usb-Adafruit_KB2040"):
            yield cls(port=port, baudrate=115200)

    def peripheral_info(self) -> PeripheralInfo:
        return PeripheralInfo(
            id=f"accelerometer:{self.port}",
            tags=[
                PeripheralTag(name="input_variant", variant="accelerometer"),
            ],
        )

    @classmethod
    def detection_node(
        cls,
        *,
        output_route: TypedRoute[SensorEvent] | None = None,
        vector_output_route: TypedRoute[SensorEvent] | None = None,
        vector_error_route: TypedRoute[BaseException] | None = None,
        spawn_sources: bool = False,
        on_detect: Any | None = None,
        start_immediately: bool = True,
    ) -> DetectionNode:
        resolved_output_route = output_route or accelerometer_detection_route()
        resolved_vector_output_route = (
            vector_output_route or accelerometer_vector_event_route()
        )

        def mapper(peripheral: "Accelerometer") -> SensorEvent:
            return SensorEvent(
                event_type="peripheral.accelerometer.detected",
                data={"port": peripheral.port, "baudrate": peripheral.baudrate},
                observed_at=time.time(),
                identity=peripheral.peripheral_info().to_sensor_identity(),
            )

        def spawn(peripheral: "Accelerometer", access: Any) -> None:
            if not spawn_sources:
                return
            access.own(
                peripheral.install_node(
                    access.graph,
                    output_route=resolved_vector_output_route,
                    error_route=vector_error_route or accelerometer_error_route(),
                )
            )

        return DetectionNode(
            name="heart-accelerometer-detection",
            detector=cls.detect,
            output_route=resolved_output_route,
            mapper=mapper,
            on_detect=on_detect,
            spawn=spawn,
            error_route=accelerometer_error_route(),
            group="accelerometer-detection",
            start_immediately=start_immediately,
        )

    def _connect_to_ser(self) -> serial.Serial:
        return serial.Serial(self.port, self.baudrate, timeout=1.0)

    def run(self) -> None:
        if self._loop_handle is not None and self._loop_handle.thread.is_alive():
            return
        loop = ManagedRunLoop(
            body=self._run_loop,
            backoff=BackoffPolicy.fixed(RECONNECT_DELAY_SECONDS),
            on_error=lambda _exc, _attempt: logger.exception(
                "Accelerometer stream failed; reconnecting"
            ),
            group="accelerometer",
        )
        self._loop_handle = loop.start_thread(
            name=ACCELEROMETER_THREAD_NAME,
            daemon=True,
        )

    def stop(self) -> None:
        if self._loop_handle is not None:
            self._loop_handle.stop()

    def _run_loop(self, stop: StopToken) -> None:
        with self._connect_to_ser() as ser:
            while not stop.is_set():
                datum = ser.readline()
                if not datum:
                    continue
                self._process_data(datum)

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
        """Install this accelerometer as a self-running Manyfold graph source."""

        resolved_output_route = output_route or accelerometer_vector_event_route()

        def _body(stop: StopToken, graph: Graph) -> None:
            try:
                with self._connect_to_ser() as ser:
                    while not stop.is_set():
                        datum = ser.readline()
                        if not datum:
                            continue
                        acceleration = self._process_data(datum)
                        if acceleration is None:
                            continue
                        graph.publish(
                            resolved_output_route,
                            self._acceleration_to_sensor_event(acceleration),
                        )
            except KeyboardInterrupt:
                stop.set()
                return

        return ManagedGraphNode(
            name="heart-accelerometer-vectors",
            body=_body,
            output_routes=(resolved_output_route,),
            error_route=error_route or accelerometer_error_route(),
            retry=retry or RetryPolicy(max_attempts=1_000_000),
            backoff=backoff or BackoffPolicy.fixed(RECONNECT_DELAY_SECONDS),
            group="accelerometer",
            start_immediately=start_immediately,
        ).install(graph)

    def _process_data(self, data: bytes) -> Acceleration | None:
        bus_data = data.decode("utf-8").rstrip()
        if not bus_data:
            return None
        if "{" not in bus_data:
            return None
        if not bus_data.startswith("{"):
            bus_data = bus_data[bus_data.find("{") :]

        try:
            parsed: dict[str, Any] = json.loads(bus_data)
        except json.JSONDecodeError:
            self._decode_failures += 1
            logger.debug("Failed to decode JSON: %s", bus_data)
            return None
        self._messages_received += 1
        self._log_controller.log(
            key="sensor.serial.poll",
            logger=logger,
            level=logging.INFO,
            msg="Sensor stream stats messages=%s decode_failures=%s",
            args=(self._messages_received, self._decode_failures),
        )
        return self._update_due_to_data(parsed)

    def get_acceleration(self) -> Acceleration | None:
        if self.acceleration_value is None:
            return None
        try:
            return Acceleration(
                self.acceleration_value["x"],
                self.acceleration_value["y"],
                self.acceleration_value["z"],
            )
        except KeyError:
            logger.warning(
                "Failed to get acceleration, data: %s", self.acceleration_value
            )
            return None


    def _update_due_to_data(self, data: dict[str, Any]) -> Acceleration | None:
        event_type = data.get("event_type")
        payload = data.get("data")
        if not isinstance(payload, dict):
            logger.debug("Ignoring malformed sensor payload: %s", payload)
            return None

        if event_type in {"acceleration", "sensor.acceleration"}:
            return self._handle_acceleration(payload)
        if event_type in {"magnetic", "sensor.magnetic"}:
            self._handle_magnetic(payload)
            return None
        logger.debug("Ignoring unknown sensor payload type: %s", event_type)
        return None

    def _handle_acceleration(self, payload: Mapping[str, Any]) -> Acceleration | None:
        try:
            vector = AccelerometerVector(
                x=float(payload["x"]),
                y=float(payload["y"]),
                z=float(payload["z"]),
            )
        except (KeyError, TypeError, ValueError):
            logger.debug("Accelerometer payload missing axis components: %s", payload)
            return None

        input_event = vector.to_input()
        self.acceleration_value = cast(dict[str, float], input_event.data)
        return Acceleration(
            x=self.acceleration_value["x"],
            y=self.acceleration_value["y"],
            z=self.acceleration_value["z"],
        )

    def _acceleration_to_sensor_event(self, acceleration: Acceleration) -> SensorEvent:
        vector = AccelerometerVector(
            x=acceleration.x,
            y=acceleration.y,
            z=acceleration.z,
        )
        return vector.to_input().to_sensor_event(
            identity=self.peripheral_info().to_sensor_identity()
        )

    def _handle_magnetic(self, payload: Mapping[str, Any]) -> None:
        logger.debug("Ignoring magnetic payload: %s", payload)
        # try:
        #     vector = MagnetometerVector(
        #         x=float(payload["x"]),
        #         y=float(payload["y"]),
        #         z=float(payload["z"]),
        #     )
        # except (KeyError, TypeError, ValueError):
        #     logger.debug("Magnetometer payload missing axis components: %s", payload)
        #     return

        # raise NotImplementedError("")

class FakeAccelerometer(Peripheral[Acceleration | None]):
    @classmethod
    def detect(cls) -> Iterator[Self]:
        yield cls()

    def peripheral_info(self) -> PeripheralInfo:
        return PeripheralInfo(
            id="fake_accelerometer",
            tags=[
                PeripheralTag(name="input_variant", variant="accelerometer"),
            ],
        )

    def _event_stream(
        self
    ) -> reactivex.Observable[Acceleration | None]:
        def random_accel(_: int) -> Acceleration:
            return Acceleration(
                x=random.random(),
                y=random.random(),
                z=9.8,
            )
        return pipe_in_background(
            interval_in_background(period=timedelta(milliseconds=500)),
            ops.map(random_accel)
        )
