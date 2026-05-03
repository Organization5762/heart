"""Compass peripheral that derives heading from magnetometer vectors."""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Iterator
from datetime import timedelta
from typing import Any, Deque, Mapping, Self

from manyfold import (DetectionNode, Graph, Layer, ManagedGraphNode,
                      ManagedGraphNodeHandle, OwnerName, Plane, Schema,
                      StreamFamily, StreamName, TypedRoute, Variant, route)
from manyfold.sensor_io import (BackoffPolicy, RetryPolicy, SensorEvent,
                                StopToken, sensor_event_schema)

import heart.utilities.reactive as reactive
from heart.peripheral.core import (Input, Peripheral, PeripheralInfo,
                                   PeripheralTag)
from heart.peripheral.input_payloads.motion import MagnetometerVector
from heart.peripheral.sensor import magnetometer_vector_event_route
from heart.utilities.logging import get_logger
from heart.utilities.reactive import operators as ops
from heart.utilities.reactive_threads import (interval_in_background,
                                              pipe_in_background)

logger = get_logger(__name__)

Vector3 = tuple[float, float, float]
COMPASS_GRAPH_OWNER = OwnerName("heart.compass")
COMPASS_GRAPH_FAMILY = StreamFamily("peripheral")


def compass_detection_route() -> TypedRoute[SensorEvent]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=COMPASS_GRAPH_OWNER,
        family=COMPASS_GRAPH_FAMILY,
        stream=StreamName("detected"),
        variant=Variant.Meta,
        schema=sensor_event_schema("HeartCompassDetectionEvent"),
    )


def compass_vector_event_route() -> TypedRoute[SensorEvent]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=COMPASS_GRAPH_OWNER,
        family=COMPASS_GRAPH_FAMILY,
        stream=StreamName("vectors"),
        variant=Variant.State,
        schema=sensor_event_schema("HeartCompassVectorEvent"),
    )


def compass_heading_event_route() -> TypedRoute[SensorEvent]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=COMPASS_GRAPH_OWNER,
        family=COMPASS_GRAPH_FAMILY,
        stream=StreamName("headings"),
        variant=Variant.State,
        schema=sensor_event_schema("HeartCompassHeadingEvent"),
    )


def compass_exception_schema() -> Schema[BaseException]:
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


def compass_error_route() -> TypedRoute[BaseException]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=COMPASS_GRAPH_OWNER,
        family=COMPASS_GRAPH_FAMILY,
        stream=StreamName("errors"),
        variant=Variant.Meta,
        schema=compass_exception_schema(),
    )


class Compass(Peripheral[Vector3 | None]):
    """Maintain a smoothed magnetic heading derived from sensor bus events."""

    def __init__(
        self,
        *,
        window_size: int = 5,
    ) -> None:
        if window_size < 1:
            raise ValueError("window_size must be at least one")

        super().__init__()
        self._window_size = window_size
        self._history: Deque[Vector3] = deque(maxlen=window_size)
        self._latest: Vector3 | None = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Peripheral API
    # ------------------------------------------------------------------
    def run(self) -> None:  # pragma: no cover - no active loop required
        """Compass reacts to event bus updates; no background loop needed."""

    @classmethod
    def detect(cls) -> Iterator[Self]:
        """Always expose a single compass peripheral."""

        yield cls()

    def peripheral_info(self) -> PeripheralInfo:
        return PeripheralInfo(
            id="compass:magnetometer",
            tags=[
                PeripheralTag(name="input_variant", variant="compass"),
            ],
        )

    @classmethod
    def detection_node(
        cls,
        *,
        output_route: TypedRoute[SensorEvent] | None = None,
        spawn_sources: bool = False,
        on_detect: Any | None = None,
        start_immediately: bool = True,
    ) -> DetectionNode:
        resolved_output_route = output_route or compass_detection_route()

        def mapper(peripheral: "Compass") -> SensorEvent:
            return SensorEvent(
                event_type="peripheral.compass.detected",
                data={"window_size": peripheral.window_size},
                observed_at=time.time(),
                identity=peripheral.peripheral_info().to_sensor_identity(),
            )

        def spawn(peripheral: "Compass", access: Any) -> None:
            if not spawn_sources:
                return
            access.own(
                peripheral.install_node(
                    access.graph,
                    start_immediately=start_immediately,
                )
            )

        return DetectionNode(
            name="heart-compass-detection",
            detector=cls.detect,
            output_route=resolved_output_route,
            mapper=mapper,
            on_detect=on_detect,
            spawn=spawn,
            error_route=compass_error_route(),
            group="compass-detection",
            start_immediately=start_immediately,
        )

    def handle_input(self, input: Input) -> None:
        if input.event_type in {
            "magnetic",
            "sensor.magnetic",
            MagnetometerVector.EVENT_TYPE,
        }:
            self._handle_magnetometer(input)

    def _handle_magnetometer(self, event: Input) -> None:
        payload = event.data
        if not isinstance(payload, Mapping):
            logger.debug("Ignoring non-mapping magnetometer payload: %s", payload)
            return

        try:
            vector = (
                float(payload["x"]),
                float(payload["y"]),
                float(payload["z"]),
            )
        except (KeyError, TypeError, ValueError):
            logger.debug("Magnetometer payload missing axis components: %s", payload)
            return

        with self._lock:
            self._latest = vector
            self._history.append(vector)

    def _event_stream(
        self
    ) -> reactive.Observable[Vector3 | None]:
        return pipe_in_background(
            interval_in_background(timedelta(milliseconds=10)),

            ops.map(lambda _: self.get_latest_vector()),
            ops.distinct_until_changed(lambda x: x)
        )

    def install_node(
        self,
        graph: Graph,
        *,
        input_route: TypedRoute[SensorEvent] | None = None,
        output_route: TypedRoute[SensorEvent] | None = None,
        heading_output_route: TypedRoute[SensorEvent] | None = None,
        error_route: TypedRoute[BaseException] | None = None,
        retry: RetryPolicy | None = None,
        backoff: BackoffPolicy | None = None,
        start_immediately: bool = True,
    ) -> ManagedGraphNodeHandle:
        """Install this compass as a Manyfold transform over magnetometer vectors."""

        resolved_input_route = input_route or magnetometer_vector_event_route()
        resolved_output_route = output_route or compass_vector_event_route()
        resolved_heading_output_route = heading_output_route or compass_heading_event_route()

        def _body(stop: StopToken, graph: Graph) -> None:
            def publish_compass_state(event: SensorEvent) -> None:
                self.handle_input(
                    Input(
                        event_type=event.event_type,
                        data=event.data,
                    )
                )
                vector = self.get_latest_vector()
                if vector is None:
                    return
                identity = self.peripheral_info().to_sensor_identity()
                observed_at = time.time()
                graph.publish(
                    resolved_output_route,
                    SensorEvent(
                        event_type="peripheral.compass.vector",
                        data={"x": vector[0], "y": vector[1], "z": vector[2]},
                        observed_at=observed_at,
                        identity=identity,
                    ),
                )
                heading = self.get_heading_degrees()
                if heading is None:
                    return
                graph.publish(
                    resolved_heading_output_route,
                    SensorEvent(
                        event_type="peripheral.compass.heading",
                        data={"degrees": heading},
                        observed_at=observed_at,
                        identity=identity,
                    ),
                )

            subscription = graph.observe(resolved_input_route).subscribe(
                lambda envelope: publish_compass_state(envelope.value)
            )
            try:
                stop.wait()
            finally:
                subscription.dispose()

        return ManagedGraphNode(
            name="heart-compass",
            body=_body,
            output_routes=(resolved_output_route, resolved_heading_output_route),
            error_route=error_route or compass_error_route(),
            retry=retry or RetryPolicy(max_attempts=1),
            backoff=backoff or BackoffPolicy.none(),
            group="compass",
            start_immediately=start_immediately,
        ).install(graph)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def get_latest_vector(self) -> Vector3 | None:
        """Return the most recent magnetic field sample."""

        with self._lock:
            return self._latest

    def get_average_vector(self) -> Vector3 | None:
        """Return the rolling average vector across the smoothing window."""

        with self._lock:
            if not self._history:
                return None
            count = len(self._history)
            x = sum(vector[0] for vector in self._history) / count
            y = sum(vector[1] for vector in self._history) / count
            z = sum(vector[2] for vector in self._history) / count
            return (x, y, z)

    def get_heading_degrees(self) -> float | None:
        """Return the smoothed magnetic heading in degrees clockwise from north."""

        vector = self.get_average_vector()
        if vector is None:
            return None

        x, y, _ = vector
        if math.isclose(x, 0.0, abs_tol=1e-9) and math.isclose(y, 0.0, abs_tol=1e-9):
            return None

        heading = math.degrees(math.atan2(x, y))
        if heading < 0:
            heading += 360.0
        return heading

    @property
    def window_size(self) -> int:
        return self._window_size
