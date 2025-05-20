from __future__ import annotations

"""PhoneText Peripheral

This peripheral exposes a single writable BLE characteristic that accepts either:
1. UTF-8 text messages (plain text sent in chunks)
2. Binary image payloads (a 64 × 64 PNG sent in 20‑byte chunks)

The most recently received image can be retrieved with `PhoneText.get_last_image()`,
and the most recently received text with `PhoneText.get_last_text()`.
"""

from pathlib import Path
from typing import Iterator, Self
import time

from heart.peripheral.core import Peripheral

try:
    # bluezero is only required when the peripheral is actually *run*.
    from bluezero import adapter, peripheral as _bz_peripheral  # type: ignore
except ModuleNotFoundError:  # pragma: no cover – only imported on the target device
    _bz_peripheral = None  # type: ignore  # noqa: N816
    adapter = None  # type: ignore

# UUIDs shared with the legacy test script so that existing iOS/Mac apps keep
# working without any change.
_SERVICE_UUID = "1234"
_CHARACTERISTIC_UUID = "5678"

# PNG signature at the start of a PNG file (to detect image data)
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# PNG end‑of‑file marker used to detect when the full image has arrived.
_PNG_EOF = b"\x00\x00\x00\x00IEND\xaeB`\x82"


class PhoneText(Peripheral):
    """Peripheral that stores the most recent text or image sent to it over BLE."""

    def __init__(self, *, persist_path: str | Path | None = None) -> None:
        """Create a new *PhoneText* peripheral.

        Parameters
        ----------
        persist_path:
            Optional path where the most-recent image should also be
            stored on disk.  If *None* (default) the image is only kept in
            memory.
        """
        self._last_image: bytes | None = None  # full PNG as received
        self._last_text: str | None = None  # full text as received
        self._buffer = bytearray()  # assembly buffer for chunks
        self._is_image_mode = False  # Track if we're receiving image data
        self._persist_path = Path(persist_path).expanduser() if persist_path else None
        super().__init__()

    # ---------------------------------------------------------------------
    # Peripheral API
    # ---------------------------------------------------------------------
    def run(self) -> None:  # noqa: D401 – keeping signature of base class
        if _bz_peripheral is None or adapter is None:
            print(
                "!!! bluezero must be installed to run PhoneText as a BLE peripheral !!!"
            )
            return

        # Pick the first Bluetooth adapter available on the host.
        hci_addr = list(adapter.Adapter.available())[0].address  # type: ignore[index]

        # Create and configure the Bluezero peripheral object.
        pi_ble = _bz_peripheral.Peripheral(hci_addr, local_name="PhoneText")
        pi_ble.add_service(1, _SERVICE_UUID, True)

        # Characteristic that the iOS application writes its data chunks into.
        pi_ble.add_characteristic(
            1,  # srv_id
            1,  # chr_id
            _CHARACTERISTIC_UUID,
            [],  # initial value (empty)
            False,  # notifying
            ["write-without-response"],
            write_callback=self._on_write,
        )

        # Start advertising – this call blocks because Bluezero enters GLib's
        # main loop internally.
        print("🔵  PhoneText peripheral advertising… (Ctrl-C to quit)")
        pi_ble.publish()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def get_last_image(self) -> bytes | None:
        """Return the most recent image that was sent to the peripheral."""
        return self._last_image

    def get_last_text(self) -> str | None:
        """Return the most recent text that was sent to the peripheral."""
        return self._last_text

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _on_write(self, value: bytes, _options: dict | None):  # noqa: D401
        """Bluezero callback executed whenever a central writes new data."""
        # Accumulate the incoming chunk
        self._buffer.extend(value)

        # First chunk detection - if buffer starts with PNG signature, it's an image
        if len(self._buffer) <= len(value) and self._buffer.startswith(_PNG_SIGNATURE):
            self._is_image_mode = True
            print("📸 Detected incoming image transfer")

        # Process based on detected mode
        if self._is_image_mode:
            self._process_image_chunk(value)
        else:
            self._process_text_chunk(value)

    def _process_image_chunk(self, value: bytes):
        """Process a chunk of image data."""
        # Look for the PNG EOF marker anywhere in the buffer
        marker_pos = self._buffer.find(_PNG_EOF)
        if marker_pos != -1:
            eof_index = marker_pos + len(_PNG_EOF)
            self._last_image = bytes(self._buffer[:eof_index])

            if self._persist_path is not None:
                try:
                    self._persist_path.write_bytes(self._last_image)
                except Exception as exc:  # pragma: no cover – best‑effort persistence
                    print(
                        f"⚠️  Could not persist last image to {self._persist_path}: {exc}"
                    )

            print(f"📥  Received complete image ({len(self._last_image)} bytes)")
            # Remove the consumed bytes and reset mode for next transfer
            self._buffer.clear()
            self._is_image_mode = False
        else:
            # Debug log for chunk reception
            print(
                f"…  Received image chunk ({len(value)} bytes, total {len(self._buffer)} bytes)"
            )

    def _process_text_chunk(self, value: bytes):
        """Process a chunk of text data.

        Text data may arrive in multiple chunks. We collect them until
        we find a null terminator or until we have a complete valid
        UTF-8 sequence (to support older apps that don't add terminators).
        """
        # Look for a null terminator (we added this in the iOS app)
        null_pos = self._buffer.find(b"\x00")

        if null_pos != -1:
            # Found terminator, extract the complete text
            try:
                text = self._buffer[:null_pos].decode("utf-8")
                self._last_text = text
                print(
                    f"📝  Received text with terminator: {text!r} ({len(text)} chars)"
                )

                # Clear buffer including the terminator
                del self._buffer[: null_pos + 1]
            except UnicodeDecodeError as e:
                print(f"⚠️  Error decoding text: {e}")
                self._buffer.clear()
        else:
            # No terminator yet - we might be mid-transmission
            try:
                # Try to decode what we have so far to see if it's complete
                text = self._buffer.decode("utf-8")

                # If we get here without exception, it's valid UTF-8
                # Check if it's been unchanged for a while (complete message)
                current_time = time.time()
                if not hasattr(self, "_last_chunk_time") or not hasattr(
                    self, "_last_buffer_size"
                ):
                    self._last_chunk_time = current_time
                    self._last_buffer_size = len(self._buffer)
                    return

                # If buffer size hasn't changed for 0.5 second, consider it complete
                if (
                    len(self._buffer) == self._last_buffer_size
                    and current_time - self._last_chunk_time > 0.5
                ):
                    self._last_text = text
                    print(
                        f"📝  Received complete text (no terminator): {text!r} ({len(text)} chars)"
                    )
                    self._buffer.clear()

                self._last_chunk_time = current_time
                self._last_buffer_size = len(self._buffer)
            except UnicodeDecodeError:
                # Still receiving chunks, keep accumulating
                print(
                    f"…  Buffering text chunk ({len(value)} bytes, total {len(self._buffer)} bytes)"
                )
                self._last_chunk_time = time.time()
                self._last_buffer_size = len(self._buffer)

    # ------------------------------------------------------------------
    # Peripheral auto-detection – integration with the *heart* framework
    # ------------------------------------------------------------------
    @staticmethod
    def detect() -> Iterator[Self]:
        """Return an iterator with a single *PhoneText* instance.

        Unlike some other peripherals we cannot *discover* a running Bluezero
        GATT server from the same process.  Therefore detection simply returns
        a single instance that, when *run()*, will start a local BLE GATT
        server.
        """
        yield PhoneText()
