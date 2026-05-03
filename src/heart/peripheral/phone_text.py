"""PhoneText Peripheral (TEXT-ONLY)

This peripheral exposes a single writable BLE characteristic that accepts UTF-8
text messages sent in one or more 20-byte chunks.  Each message must end with a
null terminator (`\0`).  The most-recent message is available via
`PhoneText.get_last_text()` for inspection by other code/tests.
"""

import time
from collections.abc import Iterator
from types import ModuleType
from typing import Any, Callable, Self, cast

from manyfold import (DetectionNode, EventStream, Graph, Layer,
                      ManagedGraphNode, ManagedGraphNodeHandle, OwnerName,
                      Plane, Schema, StreamFamily, StreamName, StreamNode,
                      TypedRoute, Variant, route)
from manyfold.sensor_io import (BackoffPolicy, RetryPolicy, SensorEvent,
                                StopToken, sensor_event_schema)

from heart.peripheral.core import Peripheral, PeripheralInfo, PeripheralTag
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
PHONE_TEXT_GRAPH_OWNER = OwnerName("heart.phone_text")
PHONE_TEXT_GRAPH_FAMILY = StreamFamily("peripheral")


def phone_text_message_route() -> TypedRoute[SensorEvent]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=PHONE_TEXT_GRAPH_OWNER,
        family=PHONE_TEXT_GRAPH_FAMILY,
        stream=StreamName("messages"),
        variant=Variant.Meta,
        schema=sensor_event_schema("HeartPhoneTextMessageEvent"),
    )


def phone_text_detection_route() -> TypedRoute[SensorEvent]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=PHONE_TEXT_GRAPH_OWNER,
        family=PHONE_TEXT_GRAPH_FAMILY,
        stream=StreamName("detected"),
        variant=Variant.Meta,
        schema=sensor_event_schema("HeartPhoneTextDetectionEvent"),
    )


def phone_text_exception_schema() -> Schema[BaseException]:
    def encode(exc: BaseException) -> bytes:
        return f"{type(exc).__name__}:{exc}".encode("utf-8")

    def decode(payload: bytes) -> BaseException:
        return RuntimeError(payload.decode("utf-8"))

    return Schema(
        schema_id="PythonException",
        version=1,
        encode=encode,
        decode=decode,
    )


def phone_text_error_route() -> TypedRoute[BaseException]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=PHONE_TEXT_GRAPH_OWNER,
        family=PHONE_TEXT_GRAPH_FAMILY,
        stream=StreamName("errors"),
        variant=Variant.Meta,
        schema=phone_text_exception_schema(),
    )


class PhoneText(Peripheral[str]):
    """Peripheral that stores the most recent text or image sent to it over BLE."""

    def __init__(self) -> None:
        """Create a new *PhoneText* peripheral."""
        super().__init__()
        self._last_text: str | None = None  # full text as received
        self.new_text = False
        self._buffer = bytearray()  # assembly buffer for chunks
        self._text_stream: EventStream[str] = EventStream()
        self._on_text: Callable[[str], None] | None = None

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

    def peripheral_info(self) -> PeripheralInfo:
        return PeripheralInfo(
            id="phone_text",
            tags=[
                PeripheralTag(name="input_variant", variant="text"),
                PeripheralTag(name="transport", variant="ble"),
            ],
        )

    @classmethod
    def detection_node(
        cls,
        *,
        detector: Any | None = None,
        output_route: TypedRoute[SensorEvent] | None = None,
        message_output_route: TypedRoute[SensorEvent] | None = None,
        message_error_route: TypedRoute[BaseException] | None = None,
        spawn_sources: bool = False,
        on_detect: Any | None = None,
        start_immediately: bool = True,
    ) -> DetectionNode:
        resolved_output_route = output_route or phone_text_detection_route()
        resolved_message_output_route = (
            message_output_route or phone_text_message_route()
        )

        def mapper(peripheral: "PhoneText") -> SensorEvent:
            return SensorEvent(
                event_type="peripheral.phone_text.detected",
                data={
                    "local_name": _LOCAL_NAME,
                    "service_uuid": _SERVICE_UUID,
                    "characteristic_uuid": _CHARACTERISTIC_UUID,
                },
                observed_at=time.time(),
                identity=peripheral.peripheral_info().to_sensor_identity(),
            )

        def spawn(peripheral: "PhoneText", access: Any) -> None:
            if not spawn_sources:
                return
            access.own(
                peripheral.install_node(
                    access.graph,
                    output_route=resolved_message_output_route,
                    error_route=message_error_route or phone_text_error_route(),
                )
            )

        return DetectionNode(
            name="heart-phone-text-detection",
            detector=detector or cls.detect,
            output_route=resolved_output_route,
            mapper=mapper,
            on_detect=on_detect,
            spawn=spawn,
            error_route=phone_text_error_route(),
            group="phone-text-detection",
            start_immediately=start_immediately,
        )

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

    def install_node(
        self,
        graph: Graph,
        *,
        output_route: TypedRoute[SensorEvent] | None = None,
        error_route: TypedRoute[BaseException] | None = None,
        retry: RetryPolicy | None = None,
        backoff: BackoffPolicy | None = None,
        start_immediately: bool = True,
    ) -> ManagedGraphNodeHandle:
        """Install this BLE text service as a Manyfold graph message source."""

        resolved_output_route = output_route or phone_text_message_route()

        def _body(stop: StopToken, graph: Graph) -> None:
            def publish_text(text: str) -> None:
                graph.publish(
                    resolved_output_route,
                    self._text_to_sensor_event(text),
                )

            previous_callback = self._on_text
            self._on_text = publish_text
            try:
                self.run()
            finally:
                self._on_text = previous_callback
                stop.set()

        return ManagedGraphNode(
            name="heart-phone-text-messages",
            body=_body,
            output_routes=(resolved_output_route,),
            error_route=error_route or phone_text_error_route(),
            retry=retry or RetryPolicy(max_attempts=1_000_000),
            backoff=backoff or BackoffPolicy.fixed(1.0),
            group="phone-text",
            start_immediately=start_immediately,
        ).install(graph)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _on_write(self, value: bytes, _options: dict[str, Any] | None) -> None:  # noqa: D401
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
        self._text_stream.emit(text)
        if self._on_text is not None:
            self._on_text(text)
        logger.info("Processed text: %r", text)

    def _event_stream(self) -> StreamNode[str]:
        return self._text_stream.observable()

    def _text_to_sensor_event(self, text: str) -> SensorEvent:
        return SensorEvent(
            event_type="peripheral.phone_text.message",
            data={"text": text},
            observed_at=time.time(),
            identity=self.peripheral_info().to_sensor_identity(),
        )

    @classmethod
    def detect(cls) -> Iterator[Self]:
        yield cls()
