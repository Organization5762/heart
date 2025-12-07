"""Frame broadcaster for WebSocket streaming."""
import asyncio
import base64
import io
import json
import queue
from typing import Set

import pygame
from fastapi import WebSocket
from PIL import Image

from heart.utilities.logging import get_logger

logger = get_logger(__name__)

# Try to import bleak for Bluetooth scanning
try:
    from bleak import BleakScanner
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False
    logger.warning("bleak not available - Bluetooth scanning disabled")


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
        
        # Input event queue for pygame
        self.input_queue: queue.Queue = queue.Queue(maxsize=100)
        
        # Track remote keyboard state (for pygame.key.get_pressed() compatibility)
        self.remote_key_state: dict[int, bool] = {}
        
        # Peripheral manager reference
        self._peripheral_manager = None
        
        # Bluetooth scan cache
        self._bluetooth_devices = []
        self._last_bt_scan = 0

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
        import time
        start = time.time()
        
        # Quick check - if no clients, skip everything
        if not self.clients:
            return

        # Store raw image for async compression (avoid blocking pygame thread)
        # The broadcast loop will handle compression
        self._latest_frame = image
        
        elapsed = time.time() - start
        if elapsed > 0.001:  # Log if >1ms
            logger.warning(f"[BROADCASTER] broadcast_frame took {elapsed*1000:.2f}ms")

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
    
    def set_peripheral_manager(self, peripheral_manager):
        """Set peripheral manager for accessing device status."""
        self._peripheral_manager = peripheral_manager
    
    async def scan_bluetooth_devices(self) -> list[dict]:
        """Scan for nearby Bluetooth devices.
        
        Returns:
            List of discovered devices with name and address.
        """
        if not BLEAK_AVAILABLE:
            return []
        
        try:
            devices = await BleakScanner.discover(timeout=2.0)
            return [
                {
                    'name': device.name or 'Unknown',
                    'address': device.address,
                    'rssi': device.rssi if hasattr(device, 'rssi') else None
                }
                for device in devices
                if device.name  # Only include devices with names
            ]
        except Exception as e:
            logger.debug(f"Bluetooth scan error: {e}")
            return []
    
    def get_peripheral_status(self) -> dict:
        """Get status of connected peripherals and bluetooth devices.
        
        Returns:
            Dictionary with device status information.
        """
        if self._peripheral_manager is None:
            return {}
        
        status = {
            'connected': [],
            'available': self._bluetooth_devices
        }
        
        # Bluetooth Switch (totem-controller)
        try:
            bt_switch = self._peripheral_manager.bluetooth_switch()
            if bt_switch and bt_switch.connected:
                status['connected'].append({
                    'name': 'totem-controller',
                    'type': 'Switch'
                })
        except Exception as e:
            logger.debug(f"Error getting bluetooth switch: {e}")
        
        # Gamepad (8bitdo)
        try:
            gamepad = self._peripheral_manager.get_gamepad()
            if gamepad and gamepad.is_connected():
                status['connected'].append({
                    'name': str(gamepad.gamepad_identifier.value),
                    'type': 'Gamepad'
                })
        except Exception as e:
            logger.debug(f"Error getting gamepad: {e}")
        
        # Phone Text
        try:
            phone_text = self._peripheral_manager.get_phone_text()
            last_text = phone_text.get_last_text()
            if last_text is not None:
                status['connected'].append({
                    'name': "SEBASTIEN's iPhone",
                    'type': 'Phone'
                })
        except Exception as e:
            logger.debug(f"Error getting phone text: {e}")
        
        return status
    
    async def handle_input(self, message: str) -> None:
        """Handle input event from a WebSocket client.
        
        Converts browser input events to pygame events and queues them.
        
        Args:
            message: JSON string containing input event data.
        """
        try:
            data = json.loads(message)
            event_type = data.get('type')
            
            if event_type == 'keydown':
                # Convert browser key to pygame event
                pygame_event = self._convert_key_event(data, pygame.KEYDOWN)
                if pygame_event:
                    self.input_queue.put_nowait(pygame_event)
                    # Track key state
                    self.remote_key_state[pygame_event.key] = True
                    logger.debug(f"Key DOWN: {pygame_event.key}, state: {self.remote_key_state}")
                    
            elif event_type == 'keyup':
                pygame_event = self._convert_key_event(data, pygame.KEYUP)
                if pygame_event:
                    self.input_queue.put_nowait(pygame_event)
                    # Track key state
                    self.remote_key_state[pygame_event.key] = False
                    logger.debug(f"Key UP: {pygame_event.key}, state: {self.remote_key_state}")
                    
            elif event_type == 'mousedown':
                pygame_event = pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,
                    {'button': data.get('button', 0) + 1, 'pos': (data.get('x', 0), data.get('y', 0))}
                )
                self.input_queue.put_nowait(pygame_event)
                
            elif event_type == 'mouseup':
                pygame_event = pygame.event.Event(
                    pygame.MOUSEBUTTONUP,
                    {'button': data.get('button', 0) + 1, 'pos': (data.get('x', 0), data.get('y', 0))}
                )
                self.input_queue.put_nowait(pygame_event)
                
            elif event_type == 'mousemove':
                pygame_event = pygame.event.Event(
                    pygame.MOUSEMOTION,
                    {'pos': (data.get('x', 0), data.get('y', 0)), 'rel': (0, 0), 'buttons': (0, 0, 0)}
                )
                self.input_queue.put_nowait(pygame_event)
                
            elif event_type == 'mousewheel':
                # Pygame 2.x supports MOUSEWHEEL events
                pygame_event = pygame.event.Event(
                    pygame.MOUSEWHEEL,
                    {'x': int(data.get('deltaX', 0)), 'y': int(-data.get('deltaY', 0))}  # Invert Y for natural scrolling
                )
                self.input_queue.put_nowait(pygame_event)
                
        except queue.Full:
            logger.warning("Input queue full, dropping event")
        except Exception as e:
            logger.error(f"Error handling input event: {e}")
    
    def _convert_key_event(self, data: dict, event_type: int) -> pygame.event.Event | None:
        """Convert browser keyboard event to pygame event.
        
        Args:
            data: Browser event data containing key, code, and modifiers.
            event_type: pygame.KEYDOWN or pygame.KEYUP
            
        Returns:
            pygame Event or None if key can't be mapped.
        """
        # Map browser KeyboardEvent.code to pygame key constants
        key_map = {
            'Escape': pygame.K_ESCAPE,
            'Space': pygame.K_SPACE,
            'Enter': pygame.K_RETURN,
            'Backspace': pygame.K_BACKSPACE,
            'Tab': pygame.K_TAB,
            'ShiftLeft': pygame.K_LSHIFT,
            'ShiftRight': pygame.K_RSHIFT,
            'ControlLeft': pygame.K_LCTRL,
            'ControlRight': pygame.K_RCTRL,
            'AltLeft': pygame.K_LALT,
            'AltRight': pygame.K_RALT,
            'ArrowUp': pygame.K_UP,
            'ArrowDown': pygame.K_DOWN,
            'ArrowLeft': pygame.K_LEFT,
            'ArrowRight': pygame.K_RIGHT,
            'BracketLeft': pygame.K_LEFTBRACKET,
            'BracketRight': pygame.K_RIGHTBRACKET,
            # Letters
            **{f'Key{chr(i)}': getattr(pygame, f'K_{chr(i).lower()}') for i in range(65, 91)},
            # Numbers
            **{f'Digit{i}': getattr(pygame, f'K_{i}') for i in range(10)},
            # F keys
            **{f'F{i}': getattr(pygame, f'K_F{i}') for i in range(1, 13)},
        }
        
        code = data.get('code', '')
        key_char = data.get('key', '')
        
        # Debug logging
        logger.debug(f"Key event: code={code}, key={key_char}")
        
        pygame_key = key_map.get(code)
        
        if pygame_key is None:
            # Try to get key from single character for unmapped keys
            if len(key_char) == 1:
                pygame_key = ord(key_char.lower())
        
        # Debug logging
        if pygame_key:
            logger.debug(f"Mapped to pygame key: {pygame_key} (code={code})")
        
        if pygame_key:
            # Build modifier mask
            mod = 0
            if data.get('shift'): mod |= pygame.KMOD_SHIFT
            if data.get('ctrl'): mod |= pygame.KMOD_CTRL
            if data.get('alt'): mod |= pygame.KMOD_ALT
            if data.get('meta'): mod |= pygame.KMOD_META
            
            return pygame.event.Event(
                event_type,
                {'key': pygame_key, 'mod': mod, 'unicode': data.get('key', '')}
            )
        
        return None
    
    def get_input_events(self) -> list:
        """Get all pending input events from the queue.
        
        Called by the pygame main loop to inject remote input events.
        
        Returns:
            List of pygame events.
        """
        events = []
        try:
            while not self.input_queue.empty():
                events.append(self.input_queue.get_nowait())
        except queue.Empty:
            pass
        return events
    
    def get_key_pressed(self, key: int) -> bool:
        """Check if a remote key is pressed.
        
        This supplements pygame.key.get_pressed() with remote keyboard state.
        
        Args:
            key: pygame key constant
            
        Returns:
            True if the remote key is pressed.
        """
        result = self.remote_key_state.get(key, False)
        if result:  # Only log when key is actually pressed to reduce noise
            logger.debug(f"get_key_pressed({key}): {result}")
        return result

    async def bluetooth_scan_loop(self) -> None:
        """Separate loop for Bluetooth scanning (non-blocking).
        
        Runs independently to avoid blocking frame broadcasting.
        """
        while True:
            if self.clients and BLEAK_AVAILABLE:
                try:
                    self._bluetooth_devices = await self.scan_bluetooth_devices()
                    logger.debug(f"Bluetooth scan found {len(self._bluetooth_devices)} devices")
                except Exception as e:
                    logger.debug(f"Bluetooth scan error: {e}")
            
            # Scan every 5 seconds
            await asyncio.sleep(5.0)
    
    async def broadcast_loop(self) -> None:
        """Continuously broadcast the latest frame to all connected clients.

        This runs in the async event loop and sends frames as they become available.
        """
        last_frame = None
        status_counter = 0
        
        while True:
            if self.clients and self._latest_frame:
                # Only compress and send if frame changed
                if self._latest_frame is not last_frame:
                    # Get compressed frame (compression happens here, not on pygame thread)
                    frame_bytes = await self.get_latest_frame()
                    
                    if frame_bytes:
                        # Send to all clients (make a copy to avoid modification during iteration)
                        async with self._lock:
                            clients_snapshot = list(self.clients)

                        disconnected = []
                        for client in clients_snapshot:
                            try:
                                # Send raw binary JPEG (no base64 encoding!)
                                await client.send_bytes(frame_bytes)
                            except Exception as e:
                                logger.warning(f"Failed to send frame to client: {e}")
                                disconnected.append(client)

                        # Remove disconnected clients
                        if disconnected:
                            async with self._lock:
                                for client in disconnected:
                                    self.clients.discard(client)
                    
                    last_frame = self._latest_frame
                
                # Send peripheral status every 30 frames (~0.5s)
                status_counter += 1
                if status_counter >= 30:
                    status_counter = 0
                    peripheral_status = self.get_peripheral_status()
                    
                    if peripheral_status:
                        async with self._lock:
                            clients_snapshot = list(self.clients)
                        
                        for client in clients_snapshot:
                            try:
                                await client.send_json({"type": "status", **peripheral_status})
                            except Exception as e:
                                logger.debug(f"Failed to send status: {e}")

            # Sleep a bit to avoid busy-waiting
            await asyncio.sleep(0.016)  # ~60fps max


