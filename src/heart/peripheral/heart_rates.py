# ant_hr_manager.py
import threading
import time
from typing import (Any, Callable, ClassVar, Dict, Iterator, List, Optional,
                    SupportsIndex, Tuple, overload)

from manyfold import (DetectionNode, Graph, Layer, ManagedGraphNode,
                      ManagedGraphNodeHandle, OwnerName, Plane, Schema,
                      StreamFamily, StreamName, TypedRoute, Variant, route)
from manyfold.rx.subject import Subject
from manyfold.sensor_io import (BackoffPolicy, RetryPolicy, SensorEvent,
                                StopToken, sensor_event_schema)
from openant.base.ant import usb
from openant.base.driver import DriverNotFound
from openant.devices import ANTPLUS_NETWORK_KEY
from openant.devices.common import DeviceType
from openant.devices.heart_rate import HeartRate, HeartRateData
from openant.devices.scanner import Scanner
from openant.devices.utilities import auto_create_device
from openant.easy.exception import AntException
from openant.easy.node import Node
from usb.core import NoBackendError

from heart.peripheral.core import Peripheral
from heart.peripheral.input_payloads import (HeartRateLifecycle,
                                             HeartRateMeasurement)
from heart.utilities.logging import get_logger

RETRY_DELAY = 5
DEVICE_TIMEOUT = 30  # seconds of silence ⇒ forget the strap
CLEANUP_INTERVAL = 5  # how often the janitor thread wakes up

BATTERY_PERCENT_SCALE = 100 / 256
HEART_RATE_GRAPH_OWNER = OwnerName("heart.heart_rate")
HEART_RATE_GRAPH_FAMILY = StreamFamily("peripheral")


class HeartRateStore:
    """Shared state store for detected heart rate monitors."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.current_bpms: Dict[str, int] = {}
        self.battery_status: Dict[str, int] = {}
        self.last_seen: Dict[str, float] = {}

    def update_from_data(self, device_id: str, data: HeartRateData) -> None:
        with self._lock:
            self.current_bpms[device_id] = data.heart_rate
            self.last_seen[device_id] = time.monotonic()
            if hasattr(data, "battery_percentage"):
                self.battery_status[device_id] = (
                    data.battery_percentage * BATTERY_PERCENT_SCALE
                )

    def prune_stale(self, now: float) -> List[str]:
        stale: List[str] = []
        with self._lock:
            for dev_id, ts in list(self.last_seen.items()):
                if now - ts > DEVICE_TIMEOUT:
                    stale.append(dev_id)

            for dev_id in stale:
                self.current_bpms.pop(dev_id, None)
                self.battery_status.pop(dev_id, None)
                self.last_seen.pop(dev_id, None)
        return stale


_STATE = HeartRateStore()

# ──────────────────────────────────────────────────────────────────────────────
current_bpms = _STATE.current_bpms
battery_status = _STATE.battery_status
last_seen = _STATE.last_seen
# ──────────────────────────────────────────────────────────────────────────────

logger = get_logger(__name__)


def heart_rate_measurement_route() -> TypedRoute[SensorEvent]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=HEART_RATE_GRAPH_OWNER,
        family=HEART_RATE_GRAPH_FAMILY,
        stream=StreamName("measurements"),
        variant=Variant.Meta,
        schema=sensor_event_schema("HeartRateMeasurementEvent"),
    )


def heart_rate_lifecycle_route() -> TypedRoute[SensorEvent]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=HEART_RATE_GRAPH_OWNER,
        family=HEART_RATE_GRAPH_FAMILY,
        stream=StreamName("lifecycle"),
        variant=Variant.Meta,
        schema=sensor_event_schema("HeartRateLifecycleEvent"),
    )


def heart_rate_detection_route() -> TypedRoute[SensorEvent]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=HEART_RATE_GRAPH_OWNER,
        family=HEART_RATE_GRAPH_FAMILY,
        stream=StreamName("detected"),
        variant=Variant.Meta,
        schema=sensor_event_schema("HeartRateDetectionEvent"),
    )


def heart_rate_exception_schema() -> Schema[BaseException]:
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


def heart_rate_error_route() -> TypedRoute[BaseException]:
    return route(
        plane=Plane.Read,
        layer=Layer.Logical,
        owner=HEART_RATE_GRAPH_OWNER,
        family=HEART_RATE_GRAPH_FAMILY,
        stream=StreamName("errors"),
        variant=Variant.Meta,
        schema=heart_rate_exception_schema(),
    )

# ---------------------------------------------------------------------------
# OpenANT sometimes has race conditions where it receives broadcast data
# before being initialized.  We wrap the list so __getitem__ never explodes.
# ---------------------------------------------------------------------------


class _DummyChannel:
    def on_broadcast_data(self, *_: object) -> None:
        pass

    def on_burst_data(self, *_: object) -> None:
        pass

    def on_acknowledge(self, *_: object) -> None:
        pass


_DUMMY = _DummyChannel()


class _SafeList(list[Any]):
    @overload
    def __getitem__(self, i: SupportsIndex) -> Any:
        ...

    @overload
    def __getitem__(self, i: slice) -> list[Any]:
        ...

    def __getitem__(self, i: SupportsIndex | slice) -> Any:
        if isinstance(i, slice):
            return super().__getitem__(i)
        index = int(i)
        if index >= len(self) or index < -len(self):
            return _DUMMY
        return super().__getitem__(index)


class HeartRateManager(Peripheral[Any]):
    """Continuously scans for ANT+ HR straps and publishes measurements."""

    EVENT_DETECTED: ClassVar[str] = "peripheral.heart_rate.detected"

    def __init__(self) -> None:
        super().__init__()
        self._node: Optional[Node] = None
        self._scanner: Optional[Scanner] = None
        self._devices: List[HeartRate] = []
        self._store = _STATE

        # Background janitor that forgets silent devices
        self._stop_evt = threading.Event()
        self._janitor = threading.Thread(
            target=self._cleanup_loop, daemon=True, name="HeartRateManager janitor"
        )
        self._janitor.start()

        self._lifecycle_status: Dict[str, str] = {}
        self._event_subject: Subject[Any] = Subject()
        self._measurement_sink: Callable[[SensorEvent], None] | None = None
        self._lifecycle_sink: Callable[[SensorEvent], None] | None = None

    # ---------- Peripheral framework ----------

    @classmethod
    def detect(cls) -> Iterator["HeartRateManager"]:
        # If this errors, we can't detect heart rate monitors on this host.
        try:
            Node()
        except DriverNotFound:
            logger.info("Unable to detect heart rate monitors - ANT driver not found")
            return
        except usb.core.NoBackendError:
            logger.info("Unable to detect heart rate monitors - USB backend not available")
            return
        yield cls()

    @classmethod
    def detection_node(
        cls,
        *,
        output_route: TypedRoute[SensorEvent] | None = None,
        measurement_output_route: TypedRoute[SensorEvent] | None = None,
        lifecycle_output_route: TypedRoute[SensorEvent] | None = None,
        source_error_route: TypedRoute[BaseException] | None = None,
        spawn_sources: bool = False,
        on_detect: Any | None = None,
        start_immediately: bool = True,
    ) -> DetectionNode:
        resolved_output_route = output_route or heart_rate_detection_route()
        resolved_measurement_route = (
            measurement_output_route or heart_rate_measurement_route()
        )
        resolved_lifecycle_route = lifecycle_output_route or heart_rate_lifecycle_route()

        def mapper(peripheral: "HeartRateManager") -> SensorEvent:
            return SensorEvent(
                event_type=cls.EVENT_DETECTED,
                data={"source": "ant_plus"},
                observed_at=time.time(),
                identity=peripheral.peripheral_info().to_sensor_identity(),
            )

        def spawn(peripheral: "HeartRateManager", access: Any) -> None:
            if not spawn_sources:
                return
            access.own(
                peripheral.install_node(
                    access.graph,
                    measurement_output_route=resolved_measurement_route,
                    lifecycle_output_route=resolved_lifecycle_route,
                    error_route=source_error_route or heart_rate_error_route(),
                )
            )

        return DetectionNode(
            name="heart-rate-detection",
            detector=cls.detect,
            output_route=resolved_output_route,
            mapper=mapper,
            on_detect=on_detect,
            spawn=spawn,
            error_route=heart_rate_error_route(),
            group="heart-rate-detection",
            start_immediately=start_immediately,
        )

    def _event_stream(self) -> Subject[Any]:
        return self._event_subject

    # ---------- Callbacks -----------------------------------------------------

    def _on_found(self, d: Tuple[int, int, int]) -> None:
        dev_id, dev_type, tx_type = d
        logger.info("Found device #%05X (%s)", dev_id, DeviceType(dev_type).name)
        try:
            hrm = auto_create_device(self._node, dev_id, dev_type, tx_type)
            hrm.on_device_data = self._cb(hrm)
            self._devices.append(hrm)
            self._emit_lifecycle(
                HeartRateLifecycle(
                    status="found",
                    device_id=f"{dev_id:05X}",
                    detail={
                        "device_type": DeviceType(dev_type).name,
                        "transmission_type": tx_type,
                    },
                )
            )
        except Exception:
            logger.exception("Could not create HR device")

    def _cb(self, hrm: HeartRate) -> Callable[[object, object, object], None]:
        def _inner(_pg: object, _name: object, data: object) -> None:
            if isinstance(data, HeartRateData):
                device_id = f"{hrm.device_id:05X}"
                measurement = self._record_measurement(device_id, data)
                event = measurement.to_input().to_sensor_event(
                    identity=self.peripheral_info().to_sensor_identity()
                )
                self._event_subject.on_next(measurement)
                if self._measurement_sink is not None:
                    self._measurement_sink(event)

                logger.debug("HR %s BPM (device %s)", data.heart_rate, device_id)

        return _inner

    def _record_measurement(
        self,
        device_id: str,
        data: HeartRateData,
    ) -> HeartRateMeasurement:
        self._store.update_from_data(device_id, data)
        battery_level = self._store.battery_status.get(device_id)
        return HeartRateMeasurement(
            device_id=device_id,
            bpm=data.heart_rate,
            battery_level=battery_level,
        )

    def _emit_lifecycle(self, lifecycle: HeartRateLifecycle) -> None:
        event = lifecycle.to_input().to_sensor_event(
            identity=self.peripheral_info().to_sensor_identity()
        )
        self._event_subject.on_next(lifecycle)
        if self._lifecycle_sink is not None:
            self._lifecycle_sink(event)

    # ---------- Janitor thread ------------------------------------------------

    def _cleanup_loop(self) -> None:
        """Drop straps that have been quiet for DEVICE_TIMEOUT seconds."""
        while not self._stop_evt.wait(CLEANUP_INTERVAL):
            stale = self._store.prune_stale(time.monotonic())
            for dev_id in stale:
                logger.info(
                    "Pruned silent HR strap %s (>%ds idle)", dev_id, DEVICE_TIMEOUT
                )
                self._emit_lifecycle(
                    HeartRateLifecycle(
                        status="stale",
                        device_id=dev_id,
                        detail={"timeout_seconds": DEVICE_TIMEOUT},
                    )
                )

    # ---------- ANT+ life-cycle ---------------------------------------------

    def _ant_cycle(self) -> None:
        self._node = Node()
        self._node.channels = _SafeList(self._node.channels)

        try:
            # 1) program ANT+ network key
            try:
                self._node.set_network_key(0x00, ANTPLUS_NETWORK_KEY)
            except AntException:
                logger.warning(
                    "Network-key ACK timed out, proceeding anyway", exc_info=True
                )

            # 2) HRM scanner
            self._scanner = Scanner(
                self._node, device_id=0, device_type=DeviceType.HeartRate.value
            )
            self._scanner.on_found = self._on_found

            # 3) start USB / RX thread
            self._node.start()

        finally:
            # always free resources
            try:
                if self._scanner:
                    self._scanner.close_channel()
                for d in self._devices:
                    d.close_channel()
            finally:
                if self._node:
                    self._node.stop()
                self._devices.clear()

    # ---------- Run loop -----------------------------------------------------

    def run(self) -> None:
        try:
            while True:
                try:
                    self._ant_cycle()
                except DriverNotFound:
                    logger.exception(
                        "ANT driver not found - skipping HeartRateManager"
                    )
                    return
                except NoBackendError:
                    logger.exception(
                        "USB backend not available - skipping HeartRateManager"
                    )
                    return
                except (AntException, OSError, RuntimeError):
                    logger.exception(
                        "ANT error: retrying in %d s", RETRY_DELAY
                    )
                    time.sleep(RETRY_DELAY)
        finally:
            self._stop_evt.set()  # stop janitor when manager exits

    def install_node(
        self,
        graph: Graph,
        *,
        measurement_output_route: TypedRoute[SensorEvent] | None = None,
        lifecycle_output_route: TypedRoute[SensorEvent] | None = None,
        error_route: TypedRoute[BaseException] | None = None,
        retry: RetryPolicy | None = None,
        backoff: BackoffPolicy | None = None,
        start_immediately: bool = True,
    ) -> ManagedGraphNodeHandle:
        """Install this ANT+ manager as a self-running Manyfold graph source."""

        resolved_measurement_route = (
            measurement_output_route or heart_rate_measurement_route()
        )
        resolved_lifecycle_route = lifecycle_output_route or heart_rate_lifecycle_route()

        def _body(stop: StopToken, graph: Graph) -> None:
            self._measurement_sink = lambda event: graph.publish(
                resolved_measurement_route,
                event,
            )
            self._lifecycle_sink = lambda event: graph.publish(
                resolved_lifecycle_route,
                event,
            )
            try:
                while not stop.is_set():
                    self._ant_cycle()
                    if not stop.is_set():
                        stop.wait(RETRY_DELAY)
            finally:
                self._measurement_sink = None
                self._lifecycle_sink = None

        return ManagedGraphNode(
            name="heart-rate-measurements",
            body=_body,
            output_routes=(resolved_measurement_route, resolved_lifecycle_route),
            error_route=error_route or heart_rate_error_route(),
            retry=retry or RetryPolicy(max_attempts=1_000_000),
            backoff=backoff or BackoffPolicy.fixed(RETRY_DELAY),
            group="heart-rate",
            start_immediately=start_immediately,
        ).install(graph)
