"""Frame broadcaster for WebSocket streaming."""
import asyncio
import base64
import io
from typing import Set

from fastapi import WebSocket
from PIL import Image

from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class FrameBroadcaster:
    """Manages WebSocket connections and broadcasts frames to all connected clients."""

    def __init__(self, jpeg_quality: int = 85):
        """Initialize the broadcaster.

        Args:
            jpeg_quality: JPEG compression quality (1-100). Lower = smaller files.
        """
        self.clients: Set[WebSocket] = set()
        self.jpeg_quality = jpeg_quality
        self._lock = asyncio.Lock()
        self._latest_frame: bytes | None = None

    async def connect(self, websocket: WebSocket) -> None:
        """Register a new WebSocket client.

        Args:
            websocket: The WebSocket connection to register.
        """
        await websocket.accept()
        async with self._lock:
            self.clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.clients)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        """Unregister a WebSocket client.

        Args:
            websocket: The WebSocket connection to unregister.
        """
        async with self._lock:
            self.clients.discard(websocket)
        logger.info(f"Client disconnected. Total clients: {len(self.clients)}")

    def broadcast_frame(self, image: Image.Image) -> None:
        """Compress and store the latest frame for broadcasting.

        This method is called from the pygame thread. It compresses the frame
        and stores it for the async broadcast loop to send.

        Args:
            image: PIL Image to broadcast.
        """
        # Quick check - if no clients, skip everything
        if not self.clients:
            return

        # Store raw image for async compression (avoid blocking pygame thread)
        # The broadcast loop will handle compression
        self._latest_frame = image

    async def get_latest_frame(self) -> bytes | None:
        """Get the latest frame for sending to clients.

        Returns:
            JPEG-encoded frame bytes, or None if no frame available.
        """
        if self._latest_frame is None:
            return None
            
        # Compress frame if it's a PIL Image (not already compressed)
        if isinstance(self._latest_frame, Image.Image):
            image = self._latest_frame
            buffer = io.BytesIO()
            
            # Convert RGBA to RGB if needed
            if image.mode == "RGBA":
                background = Image.new("RGB", image.size, (0, 0, 0))
                background.paste(image, mask=image.split()[3])
                image = background
            elif image.mode != "RGB":
                image = image.convert("RGB")

            image.save(buffer, format="JPEG", quality=self.jpeg_quality, optimize=True)
            return buffer.getvalue()
        else:
            return self._latest_frame

    def has_clients(self) -> bool:
        """Check if any clients are connected.

        Returns:
            True if at least one client is connected.
        """
        return len(self.clients) > 0

    async def broadcast_loop(self) -> None:
        """Continuously broadcast the latest frame to all connected clients.

        This runs in the async event loop and sends frames as they become available.
        """
        last_frame = None
        
        while True:
            if self.clients and self._latest_frame:
                # Only compress and send if frame changed
                if self._latest_frame is not last_frame:
                    # Get compressed frame (compression happens here, not on pygame thread)
                    frame_bytes = await self.get_latest_frame()
                    
                    if frame_bytes:
                        # Encode as base64 for JSON transport
                        frame_b64 = base64.b64encode(frame_bytes).decode("utf-8")

                        # Send to all clients (make a copy to avoid modification during iteration)
                        async with self._lock:
                            clients_snapshot = list(self.clients)

                        disconnected = []
                        for client in clients_snapshot:
                            try:
                                await client.send_json({"type": "frame", "data": frame_b64})
                            except Exception as e:
                                logger.warning(f"Failed to send frame to client: {e}")
                                disconnected.append(client)

                        # Remove disconnected clients
                        if disconnected:
                            async with self._lock:
                                for client in disconnected:
                                    self.clients.discard(client)
                    
                    last_frame = self._latest_frame

            # Sleep a bit to avoid busy-waiting
            await asyncio.sleep(0.016)  # ~60fps max


