"""FastAPI application for WebSocket frame streaming."""
import asyncio
import os
import threading
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from heart.server.broadcaster import FrameBroadcaster
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

# Global broadcaster instance
broadcaster = FrameBroadcaster(jpeg_quality=85)

# Create FastAPI app
app = FastAPI(title="Heart Display Streaming")

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "connected_clients": len(broadcaster.clients),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for streaming frames and receiving input from clients."""
    await broadcaster.connect(websocket)
    try:
        # Listen for input events from the client
        while True:
            try:
                # Wait for messages with timeout
                message = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                # Handle input event
                await broadcaster.handle_input(message)
            except asyncio.TimeoutError:
                # No message received, continue loop
                continue
    except WebSocketDisconnect:
        await broadcaster.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await broadcaster.disconnect(websocket)


# Mount static files AFTER defining specific routes
app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


def get_broadcaster() -> FrameBroadcaster:
    """Get the global broadcaster instance.

    Returns:
        The global FrameBroadcaster instance.
    """
    return broadcaster


def start_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Start the FastAPI server in a background thread.

    This function is called from the GameLoop to start the server automatically.

    Args:
        host: Host to bind to (default: 0.0.0.0 for all interfaces).
        port: Port to listen on (default: 8000).
    """
    import uvicorn

    def run_server():
        """Run the uvicorn server in a separate thread."""
        # Start the broadcast loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Start broadcast and bluetooth scan tasks (separate = non-blocking)
        loop.create_task(broadcaster.broadcast_loop())
        loop.create_task(broadcaster.bluetooth_scan_loop())

        # Run uvicorn
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="info",
            loop="asyncio",
        )
        server = uvicorn.Server(config)

        try:
            loop.run_until_complete(server.serve())
        except Exception as e:
            logger.error(f"Server error: {e}")

    # Start server in daemon thread
    server_thread = threading.Thread(target=run_server, daemon=True, name="fastapi-server")
    server_thread.start()

    logger.info(f"WebSocket streaming server started on http://{host}:{port}")


