import asyncio
import atexit
import json
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, cast

import websockets
from manyfold import (Graph, Layer, ManagedGraphNode, ManagedGraphNodeHandle,
                      OwnerName, Plane, Schema, StreamFamily, StreamName,
                      TypedRoute, Variant, route)
from manyfold.sensor_io import BackoffPolicy, RetryPolicy, StopToken
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from heart.device.beats.proto import \
    beats_streaming_pb2 as _beats_streaming_pb2
from heart.device.beats.streaming_config import (BeatsStreamingConfiguration,
                                                 QueueOverflowStrategy)
from heart.peripheral.core import (PeripheralInfo, PeripheralLocation,
                                   PeripheralMessageEnvelope, PeripheralTag)
from heart.peripheral.core.encoding import (PeripheralPayloadDecodingError,
                                            PeripheralPayloadEncoding,
                                            decode_peripheral_payload,
                                            encode_peripheral_payload)
from heart.utilities.logging import get_logger

logger = get_logger(__name__)
beats_streaming_pb2 = cast(Any, _beats_streaming_pb2)
WEBSOCKET_HOST = "localhost"
WEBSOCKET_PORT = 8765
WEBSOCKET_PING_INTERVAL_SECONDS = 20
WEBSOCKET_RETRY_DELAY_SECONDS = 1.0
CONTROL_MESSAGE_KIND = "control"
CONTROL_COMMAND_BROWSE = "browse"
CONTROL_COMMAND_ACTIVATE = "activate"
CONTROL_COMMAND_ALTERNATE = "alternate_activate"
CONTROL_COMMAND_SENSOR_UPDATE = "sensor_update"
BEATS_WEBSOCKET_OWNER = OwnerName("heart.beats.websocket")
BEATS_WEBSOCKET_FAMILY = StreamFamily("beats")


@dataclass(frozen=True)
class ControlMessage:
    command: str
    browse_step: int = 0
    sensor_key: str | None = None
    sensor_value: float | None = None
    clear: bool = False


def _encode_peripheral_message(
    envelope: PeripheralMessageEnvelope[Any],
) -> Any:
    info = envelope.peripheral_info
    tags = [
        beats_streaming_pb2.PeripheralTag(
            name=tag.name,
            variant=tag.variant,
            metadata=dict(tag.metadata),
        )
        for tag in info.tags
    ]
    encoded_payload = encode_peripheral_payload(envelope.data)
    if encoded_payload.encoding == PeripheralPayloadEncoding.PROTOBUF:
        payload_encoding = beats_streaming_pb2.PROTOBUF
    else:
        payload_encoding = beats_streaming_pb2.JSON_UTF8
    return beats_streaming_pb2.PeripheralEnvelope(
        peripheral_info=beats_streaming_pb2.PeripheralInfo(
            id=info.id or "",
            tags=tags,
            location=beats_streaming_pb2.PeripheralLocation(
                x=info.location.x,
                y=info.location.y,
                z=info.location.z,
                time=(
                    info.location.time.isoformat()
                    if info.location.time is not None
                    else ""
                ),
            ),
        ),
        payload=encoded_payload.payload,
        payload_encoding=payload_encoding,
        payload_type=encoded_payload.payload_type,
    )


def _decode_peripheral_payload_encoding(
    payload_encoding: int,
) -> PeripheralPayloadEncoding | None:
    if payload_encoding == beats_streaming_pb2.JSON_UTF8:
        return PeripheralPayloadEncoding.JSON_UTF8
    if payload_encoding == beats_streaming_pb2.PROTOBUF:
        return PeripheralPayloadEncoding.PROTOBUF
    return None


def decode_stream_envelope(frame: bytes) -> tuple[str, object] | None:
    envelope = beats_streaming_pb2.StreamEnvelope()
    try:
        envelope.ParseFromString(frame)
    except Exception:
        logger.exception("Failed to decode websocket stream envelope.")
        return None

    payload_kind = envelope.WhichOneof("payload")
    if payload_kind == "frame":
        return payload_kind, bytes(envelope.frame.png_data)

    if payload_kind == "peripheral":
        payload_encoding = _decode_peripheral_payload_encoding(
            envelope.peripheral.payload_encoding
        )
        if payload_encoding is None:
            logger.warning(
                "Unknown peripheral payload encoding: %s.",
                envelope.peripheral.payload_encoding,
            )
            return None
        try:
            decoded_payload = decode_peripheral_payload(
                envelope.peripheral.payload,
                encoding=payload_encoding,
                payload_type=envelope.peripheral.payload_type,
            )
        except PeripheralPayloadDecodingError:
            logger.exception("Failed to decode peripheral payload.")
            return None
        info = envelope.peripheral.peripheral_info
        tags = [
            PeripheralTag(
                name=tag.name,
                variant=tag.variant,
                metadata=dict(tag.metadata),
            )
            for tag in info.tags
        ]
        message = PeripheralMessageEnvelope(
            peripheral_info=PeripheralInfo(
                id=info.id or None,
                tags=tags,
                location=PeripheralLocation(
                    x=info.location.x,
                    y=info.location.y,
                    z=info.location.z,
                    time=_decode_location_time(info.location.time),
                ),
            ),
            data=decoded_payload,
        )
        return payload_kind, message

    logger.warning("Unknown websocket payload kind: %s.", payload_kind)
    return None


def decode_control_message(message: str | bytes) -> ControlMessage | None:
    try:
        parsed = json.loads(
            message.decode("utf-8") if isinstance(message, bytes) else message
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        logger.debug("Ignoring non-JSON websocket control message.")
        return None

    if not isinstance(parsed, dict):
        logger.debug("Ignoring websocket control payload with non-object body.")
        return None

    if parsed.get("kind") != CONTROL_MESSAGE_KIND:
        return None

    command = parsed.get("command")
    if command not in {
        CONTROL_COMMAND_BROWSE,
        CONTROL_COMMAND_ACTIVATE,
        CONTROL_COMMAND_ALTERNATE,
        CONTROL_COMMAND_SENSOR_UPDATE,
    }:
        logger.warning("Unknown websocket control command: %s.", command)
        return None

    browse_step = parsed.get("browse_step", 0)
    if not isinstance(browse_step, int):
        logger.warning("Invalid websocket browse_step: %r.", browse_step)
        return None

    sensor_key = parsed.get("sensor_key")
    sensor_value = parsed.get("sensor_value")
    clear = parsed.get("clear", False)
    if not isinstance(clear, bool):
        logger.warning("Invalid websocket sensor clear flag: %r.", clear)
        return None
    if command == CONTROL_COMMAND_SENSOR_UPDATE:
        if not isinstance(sensor_key, str) or not sensor_key:
            logger.warning("Missing websocket sensor key.")
            return None
        if not clear and not isinstance(sensor_value, int | float):
            logger.warning("Invalid websocket sensor value: %r.", sensor_value)
            return None
        return ControlMessage(
            command=command,
            browse_step=browse_step,
            sensor_key=sensor_key,
            sensor_value=float(sensor_value) if sensor_value is not None else None,
            clear=clear,
        )

    return ControlMessage(command=command, browse_step=browse_step)


def _peripheral_cache_key(envelope: PeripheralMessageEnvelope[Any]) -> str:
    info = envelope.peripheral_info
    if info.id:
        return info.id
    tag_key = ",".join(
        f"{tag.name}:{tag.variant}:{sorted(tag.metadata.items())}" for tag in info.tags
    )
    payload_type = type(envelope.data).__name__
    return f"{payload_type}:{tag_key}"


def _decode_location_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        logger.warning("Ignoring invalid peripheral location time: %s", value)
        return None


def _bytes_schema() -> Schema[bytes]:
    return Schema(
        schema_id="Bytes",
        version=1,
        encode=lambda payload: payload,
        decode=bytes,
    )


def _exception_schema() -> Schema[BaseException]:
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


def beats_websocket_frame_route() -> TypedRoute[bytes]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=BEATS_WEBSOCKET_OWNER,
        family=BEATS_WEBSOCKET_FAMILY,
        stream=StreamName("frames"),
        variant=Variant.Meta,
        schema=_bytes_schema(),
    )


def beats_websocket_error_route() -> TypedRoute[BaseException]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=BEATS_WEBSOCKET_OWNER,
        family=BEATS_WEBSOCKET_FAMILY,
        stream=StreamName("errors"),
        variant=Variant.Meta,
        schema=_exception_schema(),
    )


@dataclass
class BeatsWebSocketNode:
    websocket: "WebSocket"
    host: str = WEBSOCKET_HOST
    port: int = WEBSOCKET_PORT
    ping_interval: int = WEBSOCKET_PING_INTERVAL_SECONDS
    retry_delay: float = WEBSOCKET_RETRY_DELAY_SECONDS
    input_route: TypedRoute[bytes] = field(default_factory=beats_websocket_frame_route)
    error_route: TypedRoute[BaseException] = field(
        default_factory=beats_websocket_error_route
    )

    def install(self, graph: Graph) -> ManagedGraphNodeHandle:
        return ManagedGraphNode(
            name="heart-beats-websocket",
            body=lambda stop, graph: asyncio.run(self._run(stop, graph)),
            error_route=self.error_route,
            retry=RetryPolicy(max_attempts=1_000_000),
            backoff=BackoffPolicy.fixed(self.retry_delay),
            group="beats-websocket",
        ).install(graph)

    async def _run(self, stop: StopToken, graph: Graph) -> None:
        loop = asyncio.get_running_loop()
        broadcast_queue: asyncio.Queue[bytes] = asyncio.Queue(
            maxsize=self.websocket._streaming_settings.queue_max_size
        )

        def enqueue_frame(frame: bytes) -> None:
            loop.call_soon_threadsafe(
                self.websocket._enqueue_frame,
                frame,
                broadcast_queue,
            )

        subscription = graph.observe(
            self.input_route,
            replay_latest=False,
        ).callback(enqueue_frame)
        broadcast_task = asyncio.create_task(self._broadcast_worker(broadcast_queue))
        try:
            async with websockets.serve(
                self.websocket._handle_client,
                self.host,
                self.port,
                ping_interval=self.ping_interval,
            ) as server:
                self.websocket._server = server
                logger.info(
                    "Beats websocket server listening on ws://%s:%d",
                    self.host,
                    self.port,
                )
                server_closed_task = asyncio.create_task(server.wait_closed())
                stop_task = asyncio.create_task(self._wait_for_stop(stop))
                done, pending = await asyncio.wait(
                    (server_closed_task, stop_task),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                if server_closed_task in done and not stop.is_set():
                    raise RuntimeError("Beats websocket server closed unexpectedly")
        except OSError:
            logger.exception(
                "Beats websocket server failed to start; retrying in %.1fs",
                self.retry_delay,
            )
            raise
        except Exception:
            logger.exception(
                "Beats websocket server stopped unexpectedly; retrying in %.1fs",
                self.retry_delay,
            )
            raise
        finally:
            self.websocket._server = None
            subscription.dispose()
            broadcast_task.cancel()
            await asyncio.gather(broadcast_task, return_exceptions=True)

    async def _broadcast_worker(
        self,
        broadcast_queue: asyncio.Queue[bytes],
    ) -> None:
        while True:
            frame = await broadcast_queue.get()
            if not self.websocket.clients:
                continue
            clients = list(self.websocket.clients)
            results = await asyncio.gather(
                *[ws.send(frame) for ws in clients], return_exceptions=True
            )
            for ws, result in zip(clients, results, strict=True):
                if isinstance(result, (ConnectionClosedOK, ConnectionClosedError)):
                    self.websocket.clients.discard(ws)
                    continue
                if isinstance(result, Exception):
                    logger.warning("Error sending frame to client: %s", result)
                    self.websocket.clients.discard(ws)

    async def _wait_for_stop(self, stop: StopToken) -> None:
        while not stop.is_set():
            await asyncio.sleep(0.1)


@dataclass
class WebSocket:
    clients: set[Any] = field(default_factory=set, init=False)

    _instance = None
    _lock = threading.Lock()

    _server: Any = None
    _thread: threading.Thread | None = field(default=None, init=False)
    _graph: Graph = field(default_factory=Graph, init=False)
    _frame_route: TypedRoute[bytes] = field(
        default_factory=beats_websocket_frame_route,
        init=False,
    )
    _node_handle: ManagedGraphNodeHandle | None = field(default=None, init=False)
    _replay_lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _latest_frame: bytes | None = field(default=None, init=False)
    _latest_peripheral_frames: dict[str, bytes] = field(
        default_factory=dict, init=False
    )
    _control_handler: Callable[[ControlMessage], None] | None = field(
        default=None, init=False
    )
    _streaming_settings = BeatsStreamingConfiguration.settings()

    def __new__(cls, *args: Any, **kwargs: Any) -> "WebSocket":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __post_init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self._node_handle = BeatsWebSocketNode(
            websocket=self,
            input_route=self._frame_route,
        ).install(self._graph)
        self._thread = self._node_handle.loop_handle.thread
        atexit.register(self._node_handle.dispose, timeout=1)

    async def _handle_client(self, ws: Any) -> None:
        self.clients.add(ws)
        try:
            try:
                for frame in self._replay_frames():
                    await ws.send(frame)
            except (ConnectionClosedOK, ConnectionClosedError):
                logger.debug("Beats websocket client disconnected during replay send.")
                return
            async for message in ws:
                self._handle_control_message(message)
        except (ConnectionClosedOK, ConnectionClosedError):
            logger.debug("Beats websocket client disconnected.")
        finally:
            self.clients.discard(ws)

    def set_control_handler(
        self,
        handler: Callable[[ControlMessage], None] | None,
    ) -> None:
        self._control_handler = handler

    def _handle_control_message(self, message: str | bytes) -> None:
        control_message = decode_control_message(message)
        if control_message is None:
            return
        if self._control_handler is None:
            logger.debug(
                "Dropping websocket control command because no handler is registered."
            )
            return
        self._control_handler(control_message)

    def send(self, kind: str, payload: object) -> None:
        frame_bytes = self._encode_payload(kind=kind, payload=payload)
        if frame_bytes is None:
            return
        self._cache_replay_frame(kind=kind, payload=payload, frame_bytes=frame_bytes)
        self._graph.publish(self._frame_route, frame_bytes)

    def _cache_replay_frame(
        self, *, kind: str, payload: object, frame_bytes: bytes
    ) -> None:
        with self._replay_lock:
            if kind == "frame":
                self._latest_frame = frame_bytes
                return
            if kind == "peripheral" and isinstance(payload, PeripheralMessageEnvelope):
                self._latest_peripheral_frames[_peripheral_cache_key(payload)] = (
                    frame_bytes
                )

    def _replay_frames(self) -> tuple[bytes, ...]:
        with self._replay_lock:
            frames: list[bytes] = []
            if self._latest_frame is not None:
                frames.append(self._latest_frame)
            frames.extend(self._latest_peripheral_frames.values())
            return tuple(frames)

    def _enqueue_frame(self, frame: bytes, queue: asyncio.Queue[bytes]) -> None:
        if self._streaming_settings.overflow_strategy == QueueOverflowStrategy.ERROR:
            queue.put_nowait(frame)
            return

        if not queue.full():
            queue.put_nowait(frame)
            return

        if (
            self._streaming_settings.overflow_strategy
            == QueueOverflowStrategy.DROP_NEWEST
        ):
            logger.debug("Dropping websocket frame because queue is full.")
            return

        if (
            self._streaming_settings.overflow_strategy
            == QueueOverflowStrategy.DROP_OLDEST
        ):
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                logger.debug("Queue was empty while handling overflow.")
            queue.put_nowait(frame)

    def _encode_payload(self, kind: str, payload: object) -> bytes | None:
        if kind == "frame":
            if not isinstance(payload, (bytes, bytearray, memoryview)):
                logger.warning(
                    "Expected bytes payload for frame message, got %s.",
                    type(payload).__name__,
                )
                return None
            frame = beats_streaming_pb2.Frame(png_data=bytes(payload))
            envelope = beats_streaming_pb2.StreamEnvelope(frame=frame)
            return cast(bytes, envelope.SerializeToString())

        if kind == "peripheral":
            if not isinstance(payload, PeripheralMessageEnvelope):
                logger.warning(
                    "Expected PeripheralMessageEnvelope for peripheral message, got %s.",
                    type(payload).__name__,
                )
                return None
            envelope = beats_streaming_pb2.StreamEnvelope(
                peripheral=_encode_peripheral_message(payload)
            )
            return cast(bytes, envelope.SerializeToString())

        logger.warning("Unknown websocket payload kind: %s.", kind)
        return None
