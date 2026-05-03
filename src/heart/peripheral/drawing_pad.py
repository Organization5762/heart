"""In-memory model of a low-power drawing pad peripheral.

The :class:`DrawingPad` peripheral models a 6"×6" slate that supports a
battery-friendly stylus and a dedicated erase mode.  The implementation keeps
state entirely in-memory so that the rest of the runtime can experiment with the
input vocabulary before we have real hardware.  The backing grid uses a modest
48×48 resolution so updates remain cheap on slower hosts such as microcontrollers
or older Raspberry Pi models.

Each input event is expected to provide a coordinate pair.  Callers can specify
coordinates either as relative values in the ``[0.0, 1.0]`` range or in inches by
setting ``units="inches"``.  A stylus event writes pressure values into the
underlying grid, while an erase event clears a circular region.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from typing import Any, Iterator, Mapping, Self

from manyfold import (DetectionNode, Graph, Layer, ManagedGraphNode,
                      ManagedGraphNodeHandle, OwnerName, Plane, Schema,
                      StreamFamily, StreamName, TypedRoute, Variant, route)
from manyfold.sensor_io import (BackoffPolicy, RetryPolicy, SensorEvent,
                                StopToken, sensor_event_schema)

from heart.peripheral.core import (Input, Peripheral, PeripheralInfo,
                                   PeripheralTag)

DRAWING_PAD_GRAPH_OWNER = OwnerName("heart.drawing_pad")
DRAWING_PAD_GRAPH_FAMILY = StreamFamily("peripheral")


def drawing_pad_sample_event_route() -> TypedRoute[SensorEvent]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=DRAWING_PAD_GRAPH_OWNER,
        family=DRAWING_PAD_GRAPH_FAMILY,
        stream=StreamName("samples"),
        variant=Variant.Meta,
        schema=sensor_event_schema("HeartDrawingPadSampleEvent"),
    )


def drawing_pad_detection_route() -> TypedRoute[SensorEvent]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=DRAWING_PAD_GRAPH_OWNER,
        family=DRAWING_PAD_GRAPH_FAMILY,
        stream=StreamName("detected"),
        variant=Variant.Meta,
        schema=sensor_event_schema("HeartDrawingPadDetectionEvent"),
    )


def drawing_pad_exception_schema() -> Schema[BaseException]:
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


def drawing_pad_error_route() -> TypedRoute[BaseException]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=DRAWING_PAD_GRAPH_OWNER,
        family=DRAWING_PAD_GRAPH_FAMILY,
        stream=StreamName("errors"),
        variant=Variant.Meta,
        schema=drawing_pad_exception_schema(),
    )


@dataclass(slots=True)
class StylusSample:
    """Snapshot of a stylus interaction on the drawing pad."""

    x: float
    y: float
    pressure: float
    radius: float
    is_erase: bool = False


class DrawingPad(Peripheral[Any]):
    """Virtual 6"×6" drawing surface with stylus and erase support.

    Parameters
    ----------
    width_inches:
        Physical width of the pad.  Defaults to 6 inches.
    height_inches:
        Physical height of the pad.  Defaults to 6 inches.
    resolution:
        Number of discrete cells along each axis.  Higher values increase
        fidelity at the cost of additional memory and CPU when filling regions.
    polling_interval:
        Sleep duration used by :meth:`run` when idling.  The default keeps CPU
        usage negligible on single-board computers.
    """

    WIDTH_INCHES = 6.0
    HEIGHT_INCHES = 6.0
    DEFAULT_RESOLUTION = 48

    def __init__(
        self,
        *,
        width_inches: float | None = None,
        height_inches: float | None = None,
        resolution: int = DEFAULT_RESOLUTION,
        polling_interval: float = 0.1,
    ) -> None:
        if resolution <= 0:
            raise ValueError("resolution must be positive")

        self.width_inches = width_inches or self.WIDTH_INCHES
        self.height_inches = height_inches or self.HEIGHT_INCHES
        if self.width_inches <= 0 or self.height_inches <= 0:
            raise ValueError("physical dimensions must be positive")

        self.resolution = resolution
        self._grid = [
            [0.0 for _ in range(self.resolution)] for _ in range(self.resolution)
        ]
        self._stylus_history: list[StylusSample] = []
        self._sample_publishers: list[tuple[Graph, TypedRoute[SensorEvent]]] = []
        self._polling_interval = polling_interval
        self._stop = threading.Event()
        super().__init__()

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------
    def handle_input(self, input: Input) -> None:  # noqa: D401 - signature fixed
        """Process stylus or erase events and update the backing grid."""

        if input.event_type == "drawing_pad.stroke":
            self._apply_stylus(**self._parse_payload(input.data, is_erase=False))
        elif input.event_type == "drawing_pad.erase":
            self._apply_stylus(**self._parse_payload(input.data, is_erase=True))

    def apply_stylus(
        self,
        *,
        x: float,
        y: float,
        pressure: float = 1.0,
        radius: float = 0.05,
        units: str = "relative",
    ) -> None:
        """Public helper to draw with the stylus programmatically."""

        payload = {
            "x": x,
            "y": y,
            "pressure": pressure,
            "radius": radius,
            "units": units,
        }
        self._apply_stylus(**self._parse_payload(payload, is_erase=False))

    def erase(
        self,
        *,
        x: float,
        y: float,
        radius: float = 0.1,
        units: str = "relative",
    ) -> None:
        """Erase a circular area centred at ``(x, y)``."""

        payload = {
            "x": x,
            "y": y,
            "radius": radius,
            "units": units,
            "pressure": 0.0,
        }
        self._apply_stylus(**self._parse_payload(payload, is_erase=True))

    def clear(self) -> None:
        """Reset the drawing surface to its blank state."""

        for row in self._grid:
            for idx in range(len(row)):
                row[idx] = 0.0
        self._stylus_history.clear()

    def iter_rows(self) -> Iterable[Iterable[float]]:
        """Yield the grid rows – useful for snapshots in tests."""

        for row in self._grid:
            yield tuple(row)

    def last_sample(self) -> StylusSample | None:
        """Return the most recent stylus interaction, if any."""

        return self._stylus_history[-1] if self._stylus_history else None

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------
    @classmethod
    def detect(cls) -> Iterator[Self]:
        """Expose a single virtual drawing pad instance."""
        yield cls()

    def peripheral_info(self) -> PeripheralInfo:
        return PeripheralInfo(
            id="drawing_pad",
            tags=[
                PeripheralTag(name="input_variant", variant="drawing_pad"),
                PeripheralTag(name="input_mode", variant="stylus"),
            ],
        )

    @classmethod
    def detection_node(
        cls,
        *,
        detector: Any | None = None,
        output_route: TypedRoute[SensorEvent] | None = None,
        sample_output_route: TypedRoute[SensorEvent] | None = None,
        sample_error_route: TypedRoute[BaseException] | None = None,
        spawn_sources: bool = False,
        on_detect: Any | None = None,
        start_immediately: bool = True,
    ) -> DetectionNode:
        resolved_output_route = output_route or drawing_pad_detection_route()
        resolved_sample_output_route = (
            sample_output_route or drawing_pad_sample_event_route()
        )

        def mapper(peripheral: "DrawingPad") -> SensorEvent:
            return SensorEvent(
                event_type="peripheral.drawing_pad.detected",
                data={
                    "width_inches": peripheral.width_inches,
                    "height_inches": peripheral.height_inches,
                    "resolution": peripheral.resolution,
                },
                observed_at=time.time(),
                identity=peripheral.peripheral_info().to_sensor_identity(),
            )

        def spawn(peripheral: "DrawingPad", access: Any) -> None:
            if not spawn_sources:
                return
            access.own(
                peripheral.install_node(
                    access.graph,
                    output_route=resolved_sample_output_route,
                    error_route=sample_error_route or drawing_pad_error_route(),
                )
            )

        return DetectionNode(
            name="heart-drawing-pad-detection",
            detector=detector or cls.detect,
            output_route=resolved_output_route,
            mapper=mapper,
            on_detect=on_detect,
            spawn=spawn,
            error_route=drawing_pad_error_route(),
            group="drawing-pad-detection",
            start_immediately=start_immediately,
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
        """Install this virtual pad as a Manyfold-managed stylus sample source."""

        resolved_output_route = output_route or drawing_pad_sample_event_route()

        def _body(stop: StopToken, _graph: Graph) -> None:
            publisher = (graph, resolved_output_route)
            self._sample_publishers.append(publisher)
            try:
                while not stop.wait(self._polling_interval):
                    pass
            finally:
                try:
                    self._sample_publishers.remove(publisher)
                except ValueError:
                    pass

        return ManagedGraphNode(
            name="heart-drawing-pad-samples",
            body=_body,
            output_routes=(resolved_output_route,),
            error_route=error_route or drawing_pad_error_route(),
            retry=retry or RetryPolicy(max_attempts=1_000_000),
            backoff=backoff or BackoffPolicy.fixed(1.0),
            group="drawing-pad",
            start_immediately=start_immediately,
        ).install(graph)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _parse_payload(self, data: Mapping[str, Any], *, is_erase: bool) -> dict[str, Any]:
        if "x" not in data or "y" not in data:
            raise ValueError("payload must contain 'x' and 'y'")

        units = data.get("units", "relative")
        x_norm = self._normalize_coordinate(float(data["x"]), units, axis="x")
        y_norm = self._normalize_coordinate(float(data["y"]), units, axis="y")
        radius = float(data.get("radius", 0.05))
        radius_norm = self._normalize_distance(radius, units, axis="x")
        pressure = float(data.get("pressure", 1.0))

        return {
            "sample": StylusSample(
                x=x_norm,
                y=y_norm,
                pressure=pressure,
                radius=radius_norm,
                is_erase=is_erase,
            )
        }

    def _apply_stylus(self, *, sample: StylusSample) -> None:
        centre_x = self._to_index(sample.x)
        centre_y = self._to_index(sample.y)
        radius_cells = max(1, int(round(sample.radius * (self.resolution - 1))))
        affected = self._iter_indices_within_radius(centre_x, centre_y, radius_cells)

        for row_idx, col_idx in affected:
            if sample.is_erase:
                self._grid[row_idx][col_idx] = 0.0
            else:
                self._grid[row_idx][col_idx] = max(
                    0.0, min(1.0, sample.pressure)
                )

        self._stylus_history.append(sample)
        self._publish_sample(sample)

    def _publish_sample(self, sample: StylusSample) -> None:
        if not self._sample_publishers:
            return
        event = self._sample_to_sensor_event(sample)
        for graph, output_route in tuple(self._sample_publishers):
            graph.publish(output_route, event)

    def _sample_to_sensor_event(self, sample: StylusSample) -> SensorEvent:
        return SensorEvent(
            event_type="peripheral.drawing_pad.sample",
            data=asdict(sample),
            observed_at=time.time(),
            identity=self.peripheral_info().to_sensor_identity(),
        )

    def _normalize_coordinate(self, value: float, units: str, *, axis: str) -> float:
        if units == "relative":
            normalized = value
        elif units == "inches":
            inches = self.width_inches if axis == "x" else self.height_inches
            normalized = value / inches
        else:
            raise ValueError(f"Unsupported units: {units}")

        return max(0.0, min(1.0, normalized))

    def _normalize_distance(self, value: float, units: str, *, axis: str) -> float:
        if units == "relative":
            normalized = value
        elif units == "inches":
            inches = self.width_inches if axis == "x" else self.height_inches
            normalized = value / inches
        else:
            raise ValueError(f"Unsupported units: {units}")

        return max(0.0, normalized)

    def _to_index(self, normalized: float) -> int:
        return int(round(normalized * (self.resolution - 1)))

    def _iter_indices_within_radius(
        self, centre_x: int, centre_y: int, radius_cells: int
    ) -> Iterable[tuple[int, int]]:
        for row_idx in range(
            max(0, centre_y - radius_cells), min(self.resolution, centre_y + radius_cells + 1)
        ):
            for col_idx in range(
                max(0, centre_x - radius_cells),
                min(self.resolution, centre_x + radius_cells + 1),
            ):
                if self._within_radius(centre_x, centre_y, col_idx, row_idx, radius_cells):
                    yield (row_idx, col_idx)

    @staticmethod
    def _within_radius(
        centre_x: int,
        centre_y: int,
        x: int,
        y: int,
        radius: int,
    ) -> bool:
        return (x - centre_x) ** 2 + (y - centre_y) ** 2 <= radius**2
