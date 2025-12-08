import asyncio
import base64
import dataclasses
import io
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from uuid import UUID

import websockets
from PIL import Image
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from heart.device import Device

logger = logging.getLogger(__name__)


class UniversalJSONEncoder(json.JSONEncoder):
    """JSON encoder that supports dataclasses, pydantic models, enums, UUID, datetime, etc."""

    def default(self, obj):
        if dataclasses.is_dataclass(obj):
            return dataclasses.asdict(obj) # type: ignore

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
    clients: set = field(default_factory=set, init=False)

    _instance = None
    _lock = threading.Lock()

    _server = None
    _thread: threading.Thread = field(default=None, init=False) # type: ignore
    _loop: asyncio.AbstractEventLoop = field(default=None, init=False) # type: ignore
    _broadcast_queue: "asyncio.Queue[bytes]" = field(default=None, init=False)  # type: ignore

    def __new__(cls, *args, **kwargs):
        # Thread-safe singleton creation
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __post_init__(self):
        # Only run once for the singleton instance
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

        self._thread = threading.Thread(
            target=self._ws_thread_main,
            daemon=True
        )
        self._thread.start()

    # --- THREAD EVENT LOOP STARTUP ---
    def _ws_thread_main(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._broadcast_queue = asyncio.Queue()

        async def handler(ws):
            self.clients.add(ws)
            try:
                await ws.wait_closed()
            finally:
                self.clients.discard(ws)

        async def broadcast_worker():
            while True:
                frame = await self._broadcast_queue.get()
                for ws in list(self.clients):
                    try:
                        await ws.send(frame)
                    except (ConnectionClosedOK, ConnectionClosedError):
                        self.clients.discard(ws)
                    except Exception as e:
                        logger.warning(f"Error sending frame to client: {e}")
                        self.clients.discard(ws)

        async def main():
            self._server = await websockets.serve(
                handler,
                "localhost",
                8765,
                ping_interval=20,
            )
            self._loop.create_task(broadcast_worker())
            await self._server.wait_closed()

        self._loop.run_until_complete(main())

    # --- PUBLIC API ---
    def send(self, kind: str, payload):
        if self._broadcast_queue and self._loop:
            data = {"type": kind, "payload": payload}
            json_bytes = json.dumps(data, cls=UniversalJSONEncoder, sort_keys=True, indent=0).encode()

            fut = asyncio.run_coroutine_threadsafe(
                self._broadcast_queue.put(json_bytes),
                self._loop
            )
            fut.result()


@dataclass
class StreamedScreen(Device):
    def individual_display_size(self) -> tuple[int, int]:
        return (64, 64)

    def __post_init__(self) -> None:
        self.websocket = WebSocket()

    def set_image(self, image: Image.Image) -> None:
        assert image.size == self.full_display_size()
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        frame_bytes = buf.getvalue()

        self.websocket.send(
            kind="frame",
            payload=base64.b64encode(frame_bytes).decode("utf-8")
        )