import asyncio
import atexit
import threading
from dataclasses import dataclass, field
from typing import Any, cast

import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from heart.device.beats.proto import \
    beats_streaming_pb2 as _beats_streaming_pb2
from heart.device.beats.streaming_config import (BeatsStreamingConfiguration,
                                                 QueueOverflowStrategy)
from heart.peripheral.core import (PeripheralInfo, PeripheralMessageEnvelope,
                                   PeripheralTag)
from heart.peripheral.core.encoding import (PeripheralPayloadDecodingError,
                                            PeripheralPayloadEncoding,
                                            decode_peripheral_payload,
                                            encode_peripheral_payload)
from heart.utilities.logging import get_logger

logger = get_logger(__name__)
beats_streaming_pb2 = cast(Any, _beats_streaming_pb2)


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
            ),
            data=decoded_payload,
        )
        return payload_kind, message

    logger.warning("Unknown websocket payload kind: %s.", payload_kind)
    return None



@dataclass
class WebSocket:
    clients: set[Any] = field(default_factory=set, init=False)

    _instance = None
    _lock = threading.Lock()

    _server: Any = None
    _thread: threading.Thread | None = field(default=None, init=False)
    _loop: asyncio.AbstractEventLoop | None = field(default=None, init=False)
    _broadcast_queue: asyncio.Queue[bytes] | None = field(default=None, init=False)
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

        self._thread = threading.Thread(
            target=self._ws_thread_main,
            name="Beats websocket server",
        )
        atexit.register(self._thread.join, timeout=1)
        self._thread.start()

    def _ws_thread_main(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._broadcast_queue = asyncio.Queue(
            maxsize=self._streaming_settings.queue_max_size
        )
        loop = self._loop
        broadcast_queue = self._broadcast_queue
        assert loop is not None
        assert broadcast_queue is not None

        async def handler(ws: Any) -> None:
            self.clients.add(ws)
            try:
                await ws.wait_closed()
            finally:
                self.clients.discard(ws)

        async def broadcast_worker() -> None:
            while True:
                frame = await broadcast_queue.get()
                if not self.clients:
                    continue
                clients = list(self.clients)
                results = await asyncio.gather(
                    *[ws.send(frame) for ws in clients], return_exceptions=True
                )
                for ws, result in zip(clients, results, strict=True):
                    if isinstance(result, (ConnectionClosedOK, ConnectionClosedError)):
                        self.clients.discard(ws)
                        continue
                    if isinstance(result, Exception):
                        logger.warning("Error sending frame to client: %s", result)
                        self.clients.discard(ws)

        async def main() -> None:
            self._server = await websockets.serve(
                handler,
                "localhost",
                8765,
                ping_interval=20,
            )
            loop.create_task(broadcast_worker())
            await self._server.wait_closed()

        main_task = loop.create_task(main())
        loop.run_until_complete(main_task)

    def send(self, kind: str, payload: object) -> None:
        if self._broadcast_queue and self._loop:
            frame_bytes = self._encode_payload(kind=kind, payload=payload)
            if frame_bytes is None:
                return
            if self._streaming_settings.overflow_strategy == QueueOverflowStrategy.ERROR:
                if threading.current_thread() == self._thread:
                    self._enqueue_frame(frame_bytes, self._broadcast_queue)
                else:
                    future = asyncio.run_coroutine_threadsafe(
                        self._enqueue_frame_async(
                            frame_bytes, self._broadcast_queue
                        ),
                        self._loop,
                    )
                    future.result()
            else:
                self._loop.call_soon_threadsafe(
                    self._enqueue_frame, frame_bytes, self._broadcast_queue
                )

    def _enqueue_frame(self, frame: bytes, queue: asyncio.Queue[bytes]) -> None:
        if self._streaming_settings.overflow_strategy == QueueOverflowStrategy.ERROR:
            queue.put_nowait(frame)
            return

        if not queue.full():
            queue.put_nowait(frame)
            return

        if self._streaming_settings.overflow_strategy == QueueOverflowStrategy.DROP_NEWEST:
            logger.debug("Dropping websocket frame because queue is full.")
            return

        if self._streaming_settings.overflow_strategy == QueueOverflowStrategy.DROP_OLDEST:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                logger.debug("Queue was empty while handling overflow.")
            queue.put_nowait(frame)

    async def _enqueue_frame_async(
        self, frame: bytes, queue: asyncio.Queue[bytes]
    ) -> None:
        self._enqueue_frame(frame, queue)

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
