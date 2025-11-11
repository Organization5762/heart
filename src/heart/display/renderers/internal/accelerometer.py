"""Accelerometer subscription utilities for renderers."""

from __future__ import annotations

from heart.events.types import AccelerometerVector
from heart.peripheral.core import Input
from heart.peripheral.core.event_bus import EventBus, SubscriptionHandle
from heart.peripheral.core.manager import PeripheralManager
from heart.utilities.logging import get_logger

_LOGGER = get_logger(__name__)


class AccelerometerConsumer:
    """Mixin that caches accelerometer vectors for renderers."""

    def __init__(self) -> None:
        super().__init__()  # type: ignore[misc] - cooperative multiple inheritance
        self._accelerometer_event_bus: EventBus | None = None
        self._accelerometer_subscription: SubscriptionHandle | None = None
        self._latest_accelerometer: tuple[float, float, float] | None = None

    def bind_accelerometer(self, peripheral_manager: PeripheralManager) -> None:
        """Subscribe to accelerometer updates from ``peripheral_manager``."""

        if self._accelerometer_subscription is not None:
            return
        bus = getattr(peripheral_manager, "event_bus", None)
        if bus is None:
            _LOGGER.debug(
                "AccelerometerConsumer missing event bus; accelerometer data will stay static",
            )
            return
        self._accelerometer_event_bus = bus
        self._accelerometer_subscription = bus.subscribe(
            AccelerometerVector.EVENT_TYPE,
            self._handle_accelerometer_event,
        )

    def unbind_accelerometer(self) -> None:
        """Stop receiving accelerometer updates."""

        if self._accelerometer_event_bus is None or self._accelerometer_subscription is None:
            self._accelerometer_event_bus = None
            self._accelerometer_subscription = None
            return
        try:
            self._accelerometer_event_bus.unsubscribe(self._accelerometer_subscription)
        except Exception:  # pragma: no cover - defensive cleanup
            _LOGGER.exception("Failed to unsubscribe accelerometer consumer")
        finally:
            self._accelerometer_event_bus = None
            self._accelerometer_subscription = None

    def latest_acceleration(self) -> tuple[float, float, float] | None:
        """Return the most recent accelerometer vector, if any."""

        return self._latest_accelerometer

    def reset(self) -> None:
        self.unbind_accelerometer()
        super().reset()  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Hooks
    # ------------------------------------------------------------------
    def on_accelerometer_vector(self, vector: tuple[float, float, float]) -> None:
        """Hook invoked after ``vector`` is cached."""

    def _handle_accelerometer_event(self, event: Input) -> None:
        payload = event.data
        if isinstance(payload, AccelerometerVector):
            vector = (payload.x, payload.y, payload.z)
        else:
            try:
                vector = (
                    float(payload["x"]),
                    float(payload["y"]),
                    float(payload["z"]),
                )
            except (KeyError, TypeError, ValueError):
                _LOGGER.debug("Ignoring malformed accelerometer payload: %s", payload)
                return
        self._latest_accelerometer = vector
        try:
            self.on_accelerometer_vector(vector)
        except Exception:  # pragma: no cover - renderer hook failures shouldn't break bus
            _LOGGER.exception("AccelerometerConsumer hook failed")
