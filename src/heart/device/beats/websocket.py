import asyncio
import dataclasses
import json
import threading
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from heart.utilities.env import Configuration
from heart.utilities.env.enums import BeatsStreamOverflowStrategy
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class UniversalJSONEncoder(json.JSONEncoder):
    """JSON encoder that supports dataclasses, enums, UUID, datetime, and bytes."""

    def default(self, obj: object) -> object:
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj)  # type: ignore[arg-type]

        if isinstance(obj, Enum):
            return obj.value

        if isinstance(obj, UUID):
            return str(obj)

        if isinstance(obj, (datetime, date)):
            return obj.isoformat()

        if isinstance(obj, bytes):
            return obj.hex()

        return super().default(obj)


@dataclass
class WebSocket:
    clients: set[Any] = field(default_factory=set, init=False)

    _instance = None
    _lock = threading.Lock()

    _server: Any = None
    _thread: threading.Thread | None = field(default=None, init=False)
    _loop: asyncio.AbstractEventLoop | None = field(default=None, init=False)
    _broadcast_queue: asyncio.Queue[bytes] | None = field(default=None, init=False)
    _queue_maxsize: int = field(default=0, init=False)
    _overflow_strategy: BeatsStreamOverflowStrategy = field(
        default=BeatsStreamOverflowStrategy.DROP_NEWEST, init=False
    )
    _json_sort_keys: bool = field(default=True, init=False)
    _json_indent: int | None = field(default=0, init=False)

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
        self._queue_maxsize = Configuration.beats_stream_queue_size()
        self._overflow_strategy = Configuration.beats_stream_overflow_strategy()
        self._json_sort_keys = Configuration.beats_stream_json_sort_keys()
        self._json_indent = Configuration.beats_stream_json_indent()

        self._thread = threading.Thread(
            target=self._ws_thread_main,
            daemon=True,
        )
        self._thread.start()

    def _enqueue_frame(self, frame: bytes) -> None:
        if self._broadcast_queue is None:
            return
        if self._queue_maxsize > 0 and self._broadcast_queue.full():
            if self._overflow_strategy is BeatsStreamOverflowStrategy.DROP_NEWEST:
                logger.debug("Dropping websocket frame due to full queue")
                return
            if self._overflow_strategy is BeatsStreamOverflowStrategy.DROP_OLDEST:
                try:
                    self._broadcast_queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
        try:
            self._broadcast_queue.put_nowait(frame)
        except asyncio.QueueFull:
            logger.debug("Dropping websocket frame due to full queue")

    def _ws_thread_main(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._broadcast_queue = asyncio.Queue(maxsize=self._queue_maxsize)
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

        async def send_frame(ws: Any, frame: bytes) -> None:
            try:
                await ws.send(frame)
            except (ConnectionClosedOK, ConnectionClosedError):
                self.clients.discard(ws)
            except Exception as error:
                logger.warning("Error sending frame to client: %s", error)
                self.clients.discard(ws)

        async def broadcast_worker() -> None:
            while True:
                frame = await broadcast_queue.get()
                if not self.clients:
                    continue
                await asyncio.gather(
                    *(send_frame(ws, frame) for ws in list(self.clients))
                )

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
            data = {"type": kind, "payload": payload}
            dump_kwargs: dict[str, Any] = {
                "cls": UniversalJSONEncoder,
                "sort_keys": self._json_sort_keys,
            }
            if self._json_indent is not None:
                dump_kwargs["indent"] = self._json_indent
            json_bytes = json.dumps(data, **dump_kwargs).encode()

            self._loop.call_soon_threadsafe(self._enqueue_frame, json_bytes)
