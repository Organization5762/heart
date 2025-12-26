"""PhoneText Peripheral (TEXT-ONLY)

This peripheral exposes a single writable BLE characteristic that accepts UTF-8
text messages sent in one or more 20-byte chunks.  Each message must end with a
null terminator (`\0`).  The most-recent message is available via
`PhoneText.get_last_text()` for inspection by other code/tests.
"""

from collections.abc import Iterator
from types import ModuleType
from typing import Any, Self, cast

from heart.peripheral.core import Peripheral
from heart.utilities.logging import get_logger
from heart.utilities.optional_imports import optional_import

logger = get_logger(__name__)

adapter = cast(ModuleType | None, optional_import("bluezero.adapter", logger=logger))
bz_peripheral = cast(
    ModuleType | None,
    optional_import("bluezero.peripheral", logger=logger),
)

# UUIDs shared with the legacy test script so that existing iOS/Mac apps keep
# working without any change.
_SERVICE_UUID = "1235"
_CHARACTERISTIC_UUID = "5679"
_LOCAL_NAME = "PhoneText"


class PhoneText(Peripheral[str]):
    """Peripheral that stores the most recent text or image sent to it over BLE."""

    def __init__(self) -> None:
        """Create a new *PhoneText* peripheral."""
        super().__init__()
        self._last_text: str | None = None  # full text as received
        self.new_text = False
        self._buffer = bytearray()  # assembly buffer for chunks

    # ---------------------------------------------------------------------
    # Peripheral API
    # ---------------------------------------------------------------------
    def run(self) -> None:  # noqa: D401 – keeping signature of base class
        modules = self._get_bluezero_modules()
        if modules is None:
            return
        bluezero_adapter, bluezero_peripheral = modules

        hci_addr = self._select_adapter_address(bluezero_adapter)
        pi_ble = bluezero_peripheral.Peripheral(hci_addr, local_name=_LOCAL_NAME)
        self._configure_services(pi_ble)
        self._log_startup(hci_addr)

        logger.info("PhoneText peripheral advertising. (Ctrl-C to quit)")
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

        logger.debug("Received value: %r", value)
        self._buffer.extend(value)
        text_bytes = self._extract_complete_message()
        if text_bytes is None:
            return

        self._handle_message_bytes(text_bytes)

    def _get_bluezero_modules(self) -> tuple[ModuleType, ModuleType] | None:
        if adapter is None or bz_peripheral is None:
            logger.warning(
                "bluezero must be installed to run PhoneText as a BLE peripheral."
            )
            return None
        return adapter, bz_peripheral

    @staticmethod
    def _select_adapter_address(bluezero_adapter: ModuleType) -> str:
        address = list(bluezero_adapter.Adapter.available())[0].address
        return cast(str, address)

    def _configure_services(self, pi_ble: Any) -> None:
        pi_ble.add_service(1, _SERVICE_UUID, True)
        pi_ble.add_characteristic(
            1,  # srv_id
            1,  # chr_id
            _CHARACTERISTIC_UUID,
            [],  # initial value (empty)
            False,  # notifying
            ["write", "write-without-response", "encrypt-write"],
            write_callback=self._on_write,
        )

    @staticmethod
    def _log_startup(hci_addr: str) -> None:
        logger.info("Starting PhoneText peripheral.")
        logger.info("Service UUID: %s", _SERVICE_UUID)
        logger.info("Characteristic UUID: %s", _CHARACTERISTIC_UUID)
        logger.info("Adapter: %s", hci_addr)

    def _extract_complete_message(self) -> bytes | None:
        terminator_index = self._buffer.find(b"\0")
        if terminator_index == -1:
            return None
        text_bytes = bytes(self._buffer[:terminator_index])
        self._buffer.clear()
        return text_bytes

    def _handle_message_bytes(self, text_bytes: bytes) -> None:
        try:
            text = text_bytes.decode("utf-8")
        except UnicodeDecodeError as error:
            logger.warning("Error decoding text: %s", error)
            logger.debug("Raw bytes: %r", text_bytes)
            return

        self._last_text = text
        self.new_text = True
        logger.info("Processed text: %r", text)

    @classmethod
    def detect(cls) -> Iterator[Self]:
        yield cls()
