"""Peripheral exposing the current LED matrix frame"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Mapping

from manyfold import (Graph, Layer, ManagedGraphNode, ManagedGraphNodeHandle,
                      OwnerName, Plane, Schema, StreamFamily, StreamName,
                      TypedRoute, Variant, route)
from manyfold.sensor_io import (BackoffPolicy, RetryPolicy, SensorEvent,
                                StopToken, sensor_event_schema)
from PIL import Image

import heart.utilities.reactive as reactive
from heart.peripheral.core import Peripheral, PeripheralInfo, PeripheralTag
from heart.peripheral.input_payloads.display import DisplayFrame
from heart.utilities.logging import get_logger
from heart.utilities.logging_control import get_logging_controller
from heart.utilities.reactive import Subject

_LOGGER = get_logger(__name__)
DISPLAY_GRAPH_OWNER = OwnerName("heart.display")
DISPLAY_GRAPH_FAMILY = StreamFamily("peripheral")


def display_frame_event_route() -> TypedRoute[SensorEvent]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=DISPLAY_GRAPH_OWNER,
        family=DISPLAY_GRAPH_FAMILY,
        stream=StreamName("frames"),
        variant=Variant.Meta,
        schema=sensor_event_schema("HeartDisplayFrameEvent"),
    )


def display_exception_schema() -> Schema[BaseException]:
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


def display_error_route() -> TypedRoute[BaseException]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=DISPLAY_GRAPH_OWNER,
        family=DISPLAY_GRAPH_FAMILY,
        stream=StreamName("errors"),
        variant=Variant.Meta,
        schema=display_exception_schema(),
    )


class LEDMatrixDisplay(Peripheral[DisplayFrame]):
    """Virtual peripheral representing the rendered LED matrix image."""

    EVENT_FRAME = DisplayFrame.EVENT_TYPE

    def __init__(
        self,
        *,
        width: int,
        height: int,
    ) -> None:
        if width <= 0 or height <= 0:
            raise ValueError("Display dimensions must be positive")

        self._width = width
        self._height = height
        self._frame_lock = threading.Lock()
        self._latest_frame: DisplayFrame | None = None
        self._sequence = 0
        self._stop = threading.Event()
        self._frame_subject: Subject[DisplayFrame] = Subject()
        self._frame_publishers: list[tuple[Graph, TypedRoute[SensorEvent]]] = []
        self._log_controller = get_logging_controller()
        self._frame_count = 0

        super().__init__()

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def latest_frame(self) -> DisplayFrame | None:
        """Return the most recently published frame, if any."""

        with self._frame_lock:
            return self._latest_frame

    def _event_stream(self) -> reactive.Observable[DisplayFrame]:
        return self._frame_subject

    def peripheral_info(self) -> PeripheralInfo:
        return PeripheralInfo(
            id=f"led_matrix_{self._width}x{self._height}",
            tags=(
                PeripheralTag(
                    name="input_variant",
                    variant="display",
                    metadata={
                        "width": str(self._width),
                        "height": str(self._height),
                    },
                ),
            ),
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
        """Install this virtual display as a Manyfold-managed frame source."""

        resolved_output_route = output_route or display_frame_event_route()

        def _body(stop: StopToken, graph: Graph) -> None:
            publisher = (graph, resolved_output_route)
            self._frame_publishers.append(publisher)
            try:
                while not stop.wait(1.0):
                    pass
            finally:
                try:
                    self._frame_publishers.remove(publisher)
                except ValueError:
                    pass

        return ManagedGraphNode(
            name="heart-display-frames",
            body=_body,
            output_routes=(resolved_output_route,),
            error_route=error_route or display_error_route(),
            retry=retry or RetryPolicy(max_attempts=1_000_000),
            backoff=backoff or BackoffPolicy.fixed(1.0),
            group="display",
            start_immediately=start_immediately,
        ).install(graph)

    def publish_image(
        self,
        image: Image.Image,
        *,
        metadata: Mapping[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> DisplayFrame:
        """Record ``image`` as the latest frame"""

        if image.size != (self._width, self._height):
            raise ValueError(
                "Image dimensions do not match configured display size"
            )

        with self._frame_lock:
            frame = DisplayFrame.from_image(
                image,
                frame_id=self._sequence,
                metadata=metadata,
            )
            self._sequence += 1
            self._latest_frame = frame

        self._frame_count += 1
        self._frame_subject.on_next(frame)
        for graph, output_route in tuple(self._frame_publishers):
            graph.publish(
                output_route,
                frame.to_input(timestamp=timestamp).to_sensor_event(
                    identity=self.peripheral_info().to_sensor_identity(),
                    sequence_number=frame.frame_id,
                ),
            )
        self._log_controller.log(
            key="peripheral.display.frame",
            logger=_LOGGER,
            level=logging.INFO,
            msg="Published display frame id=%s size=%sx%s total=%s",
            args=(frame.frame_id, frame.width, frame.height, self._frame_count),
        )
        return frame
