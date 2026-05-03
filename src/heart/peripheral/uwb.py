from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Iterator, List, Self

import manyfold.rx as reactivex
import numpy as np
from manyfold import (DetectionNode, Graph, Layer, ManagedGraphNode,
                      ManagedGraphNodeHandle, OwnerName, Plane, Schema,
                      StreamFamily, StreamName, TypedRoute, Variant, route)
from manyfold.rx import operators as ops
from manyfold.sensor_io import (BackoffPolicy, RetryPolicy, SensorEvent,
                                StopToken, sensor_event_schema)

from heart.peripheral.core import Peripheral, PeripheralInfo, PeripheralTag
from heart.utilities.reactivex_threads import (interval_in_background,
                                               pipe_in_background)

# --- Shared types ------------------------------------------------------------

@dataclass
class BaseStationMeasurement:
    station_id: str
    x: float
    y: float
    z: float
    distance: float  # measured distance to target


@dataclass
class LocalizedTarget:
    """
    One event from the positioning system.

    - (x, y, z): estimated target position
    - stations: the set of base station positions + their measured distances
    """
    x: float
    y: float
    z: float
    stations: List[BaseStationMeasurement]


UWB_GRAPH_OWNER = OwnerName("heart.uwb")
UWB_GRAPH_FAMILY = StreamFamily("peripheral")


def uwb_position_event_route() -> TypedRoute[SensorEvent]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=UWB_GRAPH_OWNER,
        family=UWB_GRAPH_FAMILY,
        stream=StreamName("positions"),
        variant=Variant.Meta,
        schema=sensor_event_schema("HeartUWBPositionEvent"),
    )


def uwb_detection_route() -> TypedRoute[SensorEvent]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=UWB_GRAPH_OWNER,
        family=UWB_GRAPH_FAMILY,
        stream=StreamName("detected"),
        variant=Variant.Meta,
        schema=sensor_event_schema("HeartUWBDetectionEvent"),
    )


def uwb_exception_schema() -> Schema[BaseException]:
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


def uwb_error_route() -> TypedRoute[BaseException]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=UWB_GRAPH_OWNER,
        family=UWB_GRAPH_FAMILY,
        stream=StreamName("errors"),
        variant=Variant.Meta,
        schema=uwb_exception_schema(),
    )


# --- Position solver helper --------------------------------------------------

def solve_target_position(
    station_positions: list[tuple[float, float, float]],
    distances: list[float],
) -> tuple[float, float, float]:
    """
    Solve for the target's (x, y, z) using multilateration.

    station_positions: list of (xi, yi, zi)
    distances:         list of di (same order as station_positions)

    Requires at least 4 stations; more will be solved with least squares.
    """
    if len(station_positions) < 4:
        raise ValueError("Need at least 4 base stations for 3D fix")

    p = np.array(station_positions, dtype=float)  # shape (N, 3)
    d = np.array(distances, dtype=float)          # shape (N,)

    p0 = p[0]
    d0 = d[0]

    # Build linear system A * [x, y, z]^T = b
    rows = []
    rhs = []
    for i in range(1, len(p)):
        pi = p[i]
        di = d[i]

        # From (x - xi)^2 + (y - yi)^2 + (z - zi)^2 = di^2
        # subtract equation for station 0:
        # 2*(pi - p0)·[x,y,z] = (||pi||^2 - ||p0||^2) + d0^2 - di^2
        rows.append(2.0 * (pi - p0))
        rhs.append(
            (np.dot(pi, pi) - np.dot(p0, p0)) + d0**2 - di**2
        )

    A = np.vstack(rows)       # shape (N-1, 3)
    b = np.array(rhs)         # shape (N-1,)

    # Least-squares solve (works for exactly- or over-determined)
    x_hat, *_ = np.linalg.lstsq(A, b, rcond=None)
    return float(x_hat[0]), float(x_hat[1]), float(x_hat[2])


# --- Fake UWB positioning peripheral ----------------------------------------

class FakeUWBPositioning(Peripheral[LocalizedTarget | None]):
    """
    Fake positioning peripheral:
    - Defines a few fixed base stations in 3D.
    - Simulates a moving target.
    - Computes noisy distances to each base station.
    - Solves for the target's position and emits a LocalizedTarget event.
    """

    # in meters
    BASE_STATIONS: list[tuple[float, float, float]] = [
        (0.0, 0.0, 2.5),
        (5.0, 0.0, 2.5),
        (5.0, 5.0, 2.5),
        (0.0, 5.0, 2.5),
    ]

    @classmethod
    def detect(cls) -> Iterator[Self]:
        yield cls()

    @classmethod
    def detection_node(
        cls,
        *,
        output_route: TypedRoute[SensorEvent] | None = None,
        position_output_route: TypedRoute[SensorEvent] | None = None,
        position_error_route: TypedRoute[BaseException] | None = None,
        spawn_sources: bool = False,
        on_detect: Any | None = None,
        start_immediately: bool = True,
    ) -> DetectionNode:
        resolved_output_route = output_route or uwb_detection_route()
        resolved_position_output_route = (
            position_output_route or uwb_position_event_route()
        )

        def mapper(peripheral: "FakeUWBPositioning") -> SensorEvent:
            return SensorEvent(
                event_type="peripheral.uwb.detected",
                data={
                    "base_station_count": len(peripheral.BASE_STATIONS),
                    "mode": "fake",
                },
                observed_at=time.time(),
                identity=peripheral.peripheral_info().to_sensor_identity(),
            )

        def spawn(peripheral: "FakeUWBPositioning", access: Any) -> None:
            if not spawn_sources:
                return
            access.own(
                peripheral.install_node(
                    access.graph,
                    output_route=resolved_position_output_route,
                    error_route=position_error_route or uwb_error_route(),
                )
            )

        return DetectionNode(
            name="heart-uwb-detection",
            detector=cls.detect,
            output_route=resolved_output_route,
            mapper=mapper,
            on_detect=on_detect,
            spawn=spawn,
            error_route=uwb_error_route(),
            group="uwb-detection",
            start_immediately=start_immediately,
        )

    def peripheral_info(self) -> PeripheralInfo:
        return PeripheralInfo(
            id="fake_uwb_positioning",
            tags=[
                PeripheralTag(name="input_variant", variant="uwb_positioning"),
                PeripheralTag(name="input_mode", variant="xyz_multilateration"),
            ],
        )

    def _event_stream(self) -> reactivex.Observable[LocalizedTarget | None]:
        # Emit a new multilateration solution every 500 ms
        return pipe_in_background(
            interval_in_background(period=timedelta(milliseconds=500)),
            ops.map(self._sample_at_index),
        )

    def install_node(
        self,
        graph: Graph,
        *,
        output_route: TypedRoute[SensorEvent] | None = None,
        error_route: TypedRoute[BaseException] | None = None,
        retry: RetryPolicy | None = None,
        backoff: BackoffPolicy | None = None,
        sample_interval_seconds: float = 0.5,
        start_immediately: bool = True,
    ) -> ManagedGraphNodeHandle:
        """Install this positioning source as a Manyfold-managed graph node."""

        resolved_output_route = output_route or uwb_position_event_route()

        def _body(stop: StopToken, graph: Graph) -> None:
            sample_index = 0
            while not stop.is_set():
                graph.publish(
                    resolved_output_route,
                    self._target_to_sensor_event(self._sample_at_index(sample_index)),
                )
                sample_index += 1
                if sample_interval_seconds <= 0:
                    stop.set()
                    continue
                stop.wait(sample_interval_seconds)

        return ManagedGraphNode(
            name="heart-uwb-positioning",
            body=_body,
            output_routes=(resolved_output_route,),
            error_route=error_route or uwb_error_route(),
            retry=retry or RetryPolicy(max_attempts=1_000_000),
            backoff=backoff or BackoffPolicy.fixed(0.5),
            group="uwb-positioning",
            start_immediately=start_immediately,
        ).install(graph)

    def _sample_at_index(self, n: int) -> LocalizedTarget:
        # "True" target path: a slow circle in the x-y plane with fixed height
        t = n / 20.0  # time-ish index
        true_x = 2.5 + 1.0 * math.cos(t)
        true_y = 2.5 + 1.0 * math.sin(t)
        true_z = 1.0

        true_pos = np.array([true_x, true_y, true_z], dtype=float)

        # Simulate distances with some noise
        distances: list[float] = []
        station_measurements: list[BaseStationMeasurement] = []

        for idx, (sx, sy, sz) in enumerate(self.BASE_STATIONS):
            station_pos = np.array([sx, sy, sz], dtype=float)
            ideal_d = float(np.linalg.norm(true_pos - station_pos))
            noisy_d = ideal_d + random.gauss(0.0, 0.05)

            distances.append(noisy_d)
            station_measurements.append(
                BaseStationMeasurement(
                    station_id=f"bs_{idx}",
                    x=sx,
                    y=sy,
                    z=sz,
                    distance=noisy_d,
                )
            )

        # Solve for estimated target position from the noisy distances
        est_x, est_y, est_z = solve_target_position(
            self.BASE_STATIONS, distances
        )

        return LocalizedTarget(
            x=est_x,
            y=est_y,
            z=est_z,
            stations=station_measurements,
        )

    def _target_to_sensor_event(self, target: LocalizedTarget) -> SensorEvent:
        return SensorEvent(
            event_type="peripheral.uwb.position",
            data={
                "x": target.x,
                "y": target.y,
                "z": target.z,
                "stations": [
                    {
                        "station_id": station.station_id,
                        "x": station.x,
                        "y": station.y,
                        "z": station.z,
                        "distance": station.distance,
                    }
                    for station in target.stations
                ],
            },
            observed_at=time.time(),
            identity=self.peripheral_info().to_sensor_identity(),
        )
