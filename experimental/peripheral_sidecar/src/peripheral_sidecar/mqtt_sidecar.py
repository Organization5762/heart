import contextlib
import importlib
import importlib.abc
import signal
import sys
import time
from types import ModuleType
from typing import Iterable

from peripheral_sidecar import aggregators
from peripheral_sidecar.aggregators import PeripheralActionMapper
from peripheral_sidecar.config import PeripheralServiceConfig
from peripheral_sidecar.models import ActionEvent, RawPeripheralSnapshot

from heart.peripheral.core.manager import PeripheralManager
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


def _create_placeholder_mqtt() -> ModuleType:
    module = ModuleType("paho.mqtt.client")

    class _PlaceholderClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("paho-mqtt is required to run the peripheral sidecar.")

        def connect(
            self, *_args: object, **_kwargs: object
        ) -> None:  # pragma: no cover
            raise RuntimeError("paho-mqtt is required to run the peripheral sidecar.")

        def loop_start(self) -> None:  # pragma: no cover
            return None

        def loop_stop(self) -> None:  # pragma: no cover
            return None

        def disconnect(self) -> None:  # pragma: no cover
            return None

        def is_connected(self) -> bool:  # pragma: no cover
            return False

        def publish(
            self, *_args: object, **_kwargs: object
        ) -> None:  # pragma: no cover
            raise RuntimeError("paho-mqtt is required to run the peripheral sidecar.")

    setattr(module, "Client", _PlaceholderClient)
    return module


def _load_mqtt_module() -> ModuleType:
    spec = None
    with contextlib.suppress(ModuleNotFoundError):
        spec = importlib.util.find_spec("paho.mqtt.client")
    if spec is None or spec.loader is None:
        logger.warning("paho-mqtt not available; using placeholder client")
        return _create_placeholder_mqtt()

    loader = spec.loader
    if not isinstance(loader, importlib.abc.Loader):
        logger.warning("paho-mqtt loader missing exec_module; using placeholder client")
        return _create_placeholder_mqtt()

    module = importlib.util.module_from_spec(spec)
    if not isinstance(module, ModuleType):
        raise TypeError("module_from_spec returned unexpected type")
    try:
        loader.exec_module(module)
    except Exception:  # pragma: no cover - environment-specific dependency issues
        logger.warning(
            "Failed to import paho-mqtt; using placeholder client", exc_info=True
        )
        return _create_placeholder_mqtt()
    return module


mqtt = _load_mqtt_module()


class PeripheralMQTTService:
    """Sidecar process that translates raw peripheral data into MQTT actions."""

    def __init__(self, config: PeripheralServiceConfig | None = None) -> None:
        self.config = config or PeripheralServiceConfig.from_env()
        self._manager = PeripheralManager()
        self._mqtt_client = mqtt.Client(client_id=self.config.client_id)
        self._mappers: list[PeripheralActionMapper] = []
        self._running = False
        self._source_counts: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Setup helpers
    # ------------------------------------------------------------------
    def _connect_mqtt(self) -> None:
        logger.info(
            "Connecting to MQTT broker %s:%s",
            self.config.broker_host,
            self.config.broker_port,
        )
        self._mqtt_client.connect(
            self.config.broker_host,
            self.config.broker_port,
            self.config.mqtt_keepalive,
        )
        self._mqtt_client.loop_start()

    def _disconnect_mqtt(self) -> None:
        if self._mqtt_client.is_connected():
            self._mqtt_client.loop_stop()
            self._mqtt_client.disconnect()

    def _snake_case(self, name: str) -> str:
        result = []
        for char in name:
            if char.isupper() and result:
                result.append("_")
            result.append(char.lower())
        return "".join(result)

    def _register_peripherals(self) -> None:
        self._manager.detect()
        self._manager.start()

        for peripheral in self._manager.peripherals:
            source = self._allocate_source_name(peripheral)
            mappers = list(
                aggregators.build_action_mappers(peripheral, source, self.config)
            )
            if not mappers:
                logger.debug("No mappers registered for peripheral %s", source)
                continue
            logger.info(
                "Registered peripheral %s with %d mapper(s)",
                source,
                len(mappers),
            )
            self._mappers.extend(mappers)

    def _allocate_source_name(self, peripheral: object) -> str:
        base_name = self._snake_case(type(peripheral).__name__)
        count = self._source_counts.get(base_name, 0)
        self._source_counts[base_name] = count + 1
        if count == 0:
            return base_name
        return f"{base_name}.{count}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run(self) -> None:
        logger.info("Starting peripheral MQTT sidecar")
        self._connect_mqtt()
        self._register_peripherals()
        self._running = True

        try:
            while self._running:
                start = time.perf_counter()
                for mapper in list(self._mappers):
                    result = mapper.poll()
                    self._publish_raw(result.raw_snapshots)
                    self._publish_actions(result.action_events)

                elapsed = time.perf_counter() - start
                delay = max(0.0, self.config.poll_interval - elapsed)
                time.sleep(delay)
        except KeyboardInterrupt:
            logger.info("Peripheral sidecar interrupted")
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        if not self._running:
            self._disconnect_mqtt()
            return

        logger.info("Stopping peripheral MQTT sidecar")
        self._running = False
        self._disconnect_mqtt()

    # ------------------------------------------------------------------
    # MQTT publishing helpers
    # ------------------------------------------------------------------
    def _publish_raw(self, snapshots: Iterable[RawPeripheralSnapshot]) -> None:
        for snapshot in snapshots:
            payload = snapshot.to_payload()
            logger.debug(
                "Publishing raw snapshot to %s: %s",
                self.config.raw_topic,
                payload,
            )
            self._mqtt_client.publish(
                self.config.raw_topic,
                payload,
                qos=self.config.raw_qos,
            )

    def _publish_actions(self, actions: Iterable[ActionEvent]) -> None:
        for action in actions:
            payload = action.to_payload()
            logger.debug(
                "Publishing action to %s: %s",
                self.config.action_topic,
                payload,
            )
            self._mqtt_client.publish(
                self.config.action_topic,
                payload,
                qos=self.config.action_qos,
            )


def _install_signal_handlers(service: PeripheralMQTTService) -> None:
    def _handle_signal(signum: int, _frame: object | None) -> None:
        logger.info("Received signal %s, shutting down", signum)
        service.shutdown()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)


def main() -> None:
    service = PeripheralMQTTService()
    _install_signal_handlers(service)
    service.run()


if __name__ == "__main__":
    try:
        main()
    except Exception:  # pragma: no cover - best-effort shutdown for service entry point
        logger.exception("Peripheral MQTT sidecar crashed")
        sys.exit(1)
