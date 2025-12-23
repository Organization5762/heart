"""PhoneText Peripheral (TEXT-ONLY)

This peripheral exposes a single writable BLE characteristic that accepts UTF-8
text messages sent in one or more 20-byte chunks.  Each message must end with a
null terminator (`\0`).  The most-recent message is available via
`PhoneText.get_last_text()` for inspection by other code/tests.
"""

from collections.abc import Iterator
from types import ModuleType
from typing import Any, Self

from heart.peripheral.core import Peripheral

# Target iPhone information
TARGET_DEVICE_NAME = "SEBASTIEN's iPhone"

adapter: ModuleType | None
bz_peripheral: ModuleType | None

try:
    # bluezero is only required when the peripheral is actually *run*.
    from bluezero import adapter as adapter_module
    from bluezero import peripheral as peripheral_module
except ModuleNotFoundError:  # pragma: no cover – only imported on the target device
    adapter_module = None
    peripheral_module = None

adapter = adapter_module
bz_peripheral = peripheral_module

# UUIDs shared with the legacy test script so that existing iOS/Mac apps keep
# working without any change.
_SERVICE_UUID = "1235"
_CHARACTERISTIC_UUID = "5679"


class PhoneText(Peripheral[str]):
    """Peripheral that stores the most recent text or image sent to it over BLE."""

    def __init__(self) -> None:
        """Create a new *PhoneText* peripheral."""
        super().__init__()
        self._last_text: str | None = None  # full text as received
        self.new_text = False
        self._buffer = bytearray()  # assembly buffer for chunks
        self._producer_id = id(self)

    # ---------------------------------------------------------------------
    # Peripheral API
    # ---------------------------------------------------------------------
    def run(self) -> None:  # noqa: D401 – keeping signature of base class
        if bz_peripheral is None or adapter is None:
            print(
                "!!! bluezero must be installed to run PhoneText as a BLE peripheral !!!"
            )
            return

        assert adapter is not None
        assert bz_peripheral is not None

        # Pick the first Bluetooth adapter available on the host.
        hci_addr = list(adapter.Adapter.available())[0].address

        # Create and configure the Bluezero peripheral object.
        pi_ble = bz_peripheral.Peripheral(hci_addr, local_name="PhoneText")
        pi_ble.add_service(1, _SERVICE_UUID, True)

        # Print clear information about what we're using
        print("📲 Starting PhoneText peripheral with:")
        print(f"   Service UUID: {_SERVICE_UUID}")
        print(f"   Characteristic UUID: {_CHARACTERISTIC_UUID}")
        print(f"   Adapter: {hci_addr}")

        # Characteristic that the iOS application writes its data chunks into.
        pi_ble.add_characteristic(
            1,  # srv_id
            1,  # chr_id
            _CHARACTERISTIC_UUID,
            [],  # initial value (empty)
            False,  # notifying
            ["write", "write-without-response", "encrypt-write"],
            write_callback=self._on_write,
        )

        # Start advertising – this call blocks because Bluezero enters GLib's
        # main loop internally.
        print("🔵  PhoneText peripheral advertising… (Ctrl-C to quit)")
        pi_ble.publish()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------
    def get_last_text(self) -> str | None:
        """Return the most recent text that was sent to the peripheral."""
        return self._last_text

    def pop_text(self) -> str | None:
        """Return the most recent text that was sent to the peripheral and clear the
        buffer."""
        if not self.new_text:
            return None
        text = self._last_text
        self.new_text = False
        return text

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _on_write(
        self, value: bytes, _options: dict[str, Any] | None
    ) -> None:  # noqa: D401
        """Bluezero callback executed whenever a central writes new data."""

        print(f"Received value: {value!r}")
        # Accumulate the incoming chunk and process as text only
        self._buffer.extend(value)

        # Check if the buffer contains a null terminator which indicates end of message
        if b"\0" in self._buffer:
            # Split at the null terminator and take everything before it
            text_bytes = self._buffer[: self._buffer.index(b"\0")]
            try:
                # Convert buffer to string
                text = text_bytes.decode("utf-8")
                # Save the received text
                self._last_text = text
                self.new_text = True
                print(f"Processed text: '{text}'")
            except UnicodeDecodeError as e:
                print(f"Error decoding text: {e}")
                print(f"Raw bytes: {text_bytes}")

            # Clear the buffer for the next message
            self._buffer.clear()


    @classmethod
    def detect(cls) -> Iterator[Self]:
        yield cls()
