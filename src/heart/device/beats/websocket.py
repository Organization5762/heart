import asyncio
import dataclasses
import json
import threading
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Mapping, Sequence
from uuid import UUID

import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from heart.device.beats.proto import beats_streaming_pb2
from heart.device.beats.streaming_config import (BeatsStreamingConfiguration,
                                                 QueueOverflowStrategy)
from heart.peripheral.core import PeripheralMessageEnvelope
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


def _normalize_payload(payload: object) -> object:
    if dataclasses.is_dataclass(payload):
        return dataclasses.asdict(payload)  # type: ignore[arg-type]

    if isinstance(payload, Enum):
        return payload.value

    if isinstance(payload, UUID):
        return str(payload)

    if isinstance(payload, (datetime, date)):
        return payload.isoformat()

    if isinstance(payload, bytes):
        return payload.hex()

    if isinstance(payload, Mapping):
        return {
            str(key): _normalize_payload(value)
            for key, value in payload.items()
        }

    if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        return [_normalize_payload(value) for value in payload]

    return payload


def _encode_peripheral_message(
    envelope: PeripheralMessageEnvelope[Any],
) -> beats_streaming_pb2.PeripheralEnvelope:
    info = envelope.peripheral_info
    tags = [
        beats_streaming_pb2.PeripheralTag(
            name=tag.name,
            variant=tag.variant,
            metadata=dict(tag.metadata),
        )
        for tag in info.tags
    ]
    normalized = _normalize_payload(envelope.data)
    json_payload = json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return beats_streaming_pb2.PeripheralEnvelope(
        peripheral_info=beats_streaming_pb2.PeripheralInfo(
            id=info.id or "",
            tags=tags,
        ),
        payload=json_payload,
        payload_encoding=beats_streaming_pb2.JSON_UTF8,
    )


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
            daemon=True,
        )
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

        loop.run_until_complete(main())

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
            return envelope.SerializeToString()

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
            return envelope.SerializeToString()

        logger.warning("Unknown websocket payload kind: %s.", kind)
        return None
