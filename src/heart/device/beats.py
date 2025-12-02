import asyncio
import io
import threading
from dataclasses import dataclass, field

import websockets
from PIL import Image
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from heart.device import Device
from heart.loop import logger


@dataclass
class StreamedScreen(Device):
    clients: set = field(default_factory=set, init=False)
    _server = None
    _thread: threading.Thread = field(default=None, init=False)
    _loop: asyncio.AbstractEventLoop = field(default=None, init=False)
    _broadcast_queue: "asyncio.Queue[bytes]" = field(default=None, init=False)

    def individual_display_size(self) -> tuple[int, int]:
        return (64, 64)

    def __post_init__(self) -> None:
        self._thread = threading.Thread(target=self._ws_thread_main, daemon=True)
        self._thread.start()

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
                # Make a copy so we can safely modify self.clients
                for ws in list(self.clients):
                    try:
                        await ws.send(frame)
                    except (ConnectionClosedOK, ConnectionClosedError):
                        # Socket is closed or closing; drop it so we don't try again
                        self.clients.discard(ws)
                    except Exception as e:
                        # Log unexpected problems and also drop the client
                        logger.warning(f"Error sending frame to client: {e}")
                        self.clients.discard(ws)

        async def main():
            self._server = await websockets.serve(
                handler,
                "localhost",
                8765,
                ping_interval=20,
            )
            # Run broadcast loop in background
            self._loop.create_task(broadcast_worker())
            await self._server.wait_closed()

        self._loop.run_until_complete(main())

    def set_image(self, image: Image.Image) -> None:
        assert image.size == self.full_display_size()
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        frame_bytes = buf.getvalue()

        # enqueue for broadcast in WS thread
        if self._broadcast_queue is not None and self._loop is not None:
            # thread-safe put into the loop’s queue
            fut = asyncio.run_coroutine_threadsafe(
                self._broadcast_queue.put(frame_bytes),
                self._loop,
            )
            fut.result()