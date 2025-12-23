# ant_hr_manager.py
import logging
import threading
import time
from typing import (Any, Callable, Dict, Iterator, List, Optional,
                    SupportsIndex, Tuple, overload)

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
from heart.utilities.logging import get_logger

RETRY_DELAY = 5
DEVICE_TIMEOUT = 30  # seconds of silence ⇒ forget the strap
CLEANUP_INTERVAL = 5  # how often the janitor thread wakes up

# ──────────────────────────────────────────────────────────────────────────────
current_bpms: Dict[str, int] = {}
battery_status: Dict[str, int] = {}
last_seen: Dict[str, float] = {}  # NEW: last packet time-stamp
_mutex = threading.Lock()  # protects the three dicts above
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = get_logger("HeartRateManager")

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

    def __init__(self) -> None:
        super().__init__()
        self._node: Optional[Node] = None
        self._scanner: Optional[Scanner] = None
        self._devices: List[HeartRate] = []

        # Background janitor that forgets silent devices
        self._stop_evt = threading.Event()
        self._janitor = threading.Thread(
            target=self._cleanup_loop, daemon=True, name="HeartRateManager janitor"
        )
        self._janitor.start()

        self._lifecycle_status: Dict[str, str] = {}

    # ---------- Peripheral framework ----------

    @classmethod
    def detect(cls) -> Iterator["HeartRateManager"]:
        yield cls()

    # ---------- Callbacks -----------------------------------------------------

    def _on_found(self, d: Tuple[int, int, int]) -> None:
        dev_id, dev_type, tx_type = d
        logger.info("Found device #%05X (%s)", dev_id, DeviceType(dev_type).name)
        try:
            hrm = auto_create_device(self._node, dev_id, dev_type, tx_type)
            hrm.on_device_data = self._cb(hrm)
            self._devices.append(hrm)
        except Exception as e:
            logger.error("Could not create HR device: %s", e)

    def _cb(self, hrm: HeartRate) -> Callable[[object, object, object], None]:
        def _inner(_pg: object, _name: object, data: object) -> None:
            if isinstance(data, HeartRateData):
                device_id = f"{hrm.device_id:05X}"
                with _mutex:
                    current_bpms[device_id] = data.heart_rate
                    last_seen[device_id] = time.time()
                    if hasattr(data, "battery_percentage"):
                        battery_status[device_id] = data.battery_percentage * 100 / 256

                logger.debug("HR %s BPM (device %s)", data.heart_rate, device_id)

        return _inner

    # ---------- Janitor thread ------------------------------------------------

    def _cleanup_loop(self) -> None:
        """Drop straps that have been quiet for DEVICE_TIMEOUT seconds."""
        while not self._stop_evt.wait(CLEANUP_INTERVAL):
            now = time.time()
            stale: List[str] = []
            with _mutex:
                for dev_id, ts in list(last_seen.items()):
                    if now - ts > DEVICE_TIMEOUT:
                        stale.append(dev_id)

                for dev_id in stale:
                    current_bpms.pop(dev_id, None)
                    battery_status.pop(dev_id, None)
                    last_seen.pop(dev_id, None)
                    logger.info(
                        "Pruned silent HR strap %s (>%ds idle)", dev_id, DEVICE_TIMEOUT
                    )

    # ---------- ANT+ life-cycle ---------------------------------------------

    def _ant_cycle(self) -> None:
        self._node = Node()
        self._node.channels = _SafeList(self._node.channels)

        try:
            # 1) program ANT+ network key
            try:
                self._node.set_network_key(0x00, ANTPLUS_NETWORK_KEY)
            except AntException as e:
                logger.warning("Network-key ACK timed out, proceeding anyway (%s)", e)

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
                    logger.error("ANT driver not found - skipping HeartRateManager")
                    return
                except NoBackendError:
                    logger.error(
                        "USB backend not available - skipping HeartRateManager"
                    )
                    return
                except (AntException, OSError, RuntimeError) as e:
                    logger.error("ANT error: %s – retrying in %d s", e, RETRY_DELAY)
                    time.sleep(RETRY_DELAY)
        finally:
            self._stop_evt.set()  # stop janitor when manager exits
