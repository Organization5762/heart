from __future__ import annotations

import os
import socket
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import final

from manyfold.architecture import (MachineSignerClient, NodeIdentity,
                                   ProcessCredentialState,
                                   ProcessCredentialStatus)

from heart.utilities.logging import get_logger

DEFAULT_POLL_INTERVAL_SECONDS = 1.0
DEFAULT_RETRY_DELAY_SECONDS = 0.05
DEFAULT_RETRY_MAX_ATTEMPTS = 5
DEFAULT_SIGNER_SOCKET = Path("/run/heart-manyfold/signer.sock")
ENV_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
MAX_RETRY_DELAY_SECONDS = 1.0
MAX_RETRY_ATTEMPTS = 5

logger = get_logger(__name__)


@final
@dataclass(frozen=True, slots=True)
class ManyfoldSignerConfig:
    """Heart-owned environment boundary for Manyfold process credentials."""

    enabled: bool
    socket_path: Path
    cluster_id: str
    node_id: str
    poll_interval_seconds: float = DEFAULT_POLL_INTERVAL_SECONDS
    retry_max_attempts: int = DEFAULT_RETRY_MAX_ATTEMPTS
    retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS

    def __post_init__(self) -> None:
        if not self.cluster_id.strip():
            raise ValueError("cluster_id must be non-empty")
        if not self.node_id.strip():
            raise ValueError("node_id must be non-empty")
        if (
            isinstance(self.poll_interval_seconds, bool)
            or not isinstance(self.poll_interval_seconds, int | float)
            or self.poll_interval_seconds <= 0
        ):
            raise ValueError("poll_interval_seconds must be positive")
        if (
            isinstance(self.retry_delay_seconds, bool)
            or not isinstance(self.retry_delay_seconds, int | float)
            or not 0 <= self.retry_delay_seconds <= MAX_RETRY_DELAY_SECONDS
        ):
            raise ValueError("retry_delay_seconds must be between 0 and 1")
        if (
            isinstance(self.retry_max_attempts, bool)
            or not isinstance(self.retry_max_attempts, int)
            or not 1 <= self.retry_max_attempts <= MAX_RETRY_ATTEMPTS
        ):
            raise ValueError("retry_max_attempts must be between 1 and 5")

    @classmethod
    def from_environment(cls) -> ManyfoldSignerConfig:
        """Load only endpoint, identity, and bounded lifecycle policy."""
        hostname = socket.gethostname()
        return cls(
            enabled=_environment_flag("HEART_MANYFOLD_SIGNER_ENABLED"),
            socket_path=Path(
                os.environ.get(
                    "HEART_MANYFOLD_SIGNER_SOCKET",
                    str(DEFAULT_SIGNER_SOCKET),
                )
            ),
            cluster_id=os.environ.get("HEART_MANYFOLD_CLUSTER_ID", "heart"),
            node_id=os.environ.get("HEART_MANYFOLD_NODE_ID", hostname),
            poll_interval_seconds=_environment_float(
                "HEART_MANYFOLD_SIGNER_POLL_INTERVAL_SECONDS",
                DEFAULT_POLL_INTERVAL_SECONDS,
            ),
            retry_max_attempts=_environment_int(
                "HEART_MANYFOLD_SIGNER_RETRY_MAX_ATTEMPTS",
                DEFAULT_RETRY_MAX_ATTEMPTS,
            ),
            retry_delay_seconds=_environment_float(
                "HEART_MANYFOLD_SIGNER_RETRY_DELAY_SECONDS",
                DEFAULT_RETRY_DELAY_SECONDS,
            ),
        )


@final
class ManyfoldSignerRuntime:
    """Start, renew, and close Heart's process credential."""

    def __init__(
        self,
        config: ManyfoldSignerConfig | None = None,
    ) -> None:
        self.config = config or ManyfoldSignerConfig.from_environment()
        self._client = (
            MachineSignerClient(
                self.config.socket_path,
                NodeIdentity(self.config.cluster_id, self.config.node_id),
            )
            if self.config.enabled
            else None
        )
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_status: ProcessCredentialStatus | None = None
        self._lock = threading.RLock()

    @property
    def is_enabled(self) -> bool:
        return self._client is not None

    def start(self) -> ProcessCredentialStatus | None:
        """Require initial readiness before Heart enters the game loop."""
        with self._lock:
            if self._client is None:
                return None
            if self._thread is not None:
                return self._last_status
            try:
                signer_status = self._client.status()
            except (
                ConnectionError,
                OSError,
                RuntimeError,
                TimeoutError,
                ValueError,
            ):
                # Manyfold records the explicit unavailable lifecycle state on
                # its bounded credential path, including peer-auth rejection.
                self._client.ensure_process_credentials(
                    max_attempts=self.config.retry_max_attempts,
                    retry_delay_seconds=self.config.retry_delay_seconds,
                )
                signer_status = self._client.status()
            observed_identity = (
                signer_status.get("cluster_id"),
                signer_status.get("node_id"),
            )
            expected_identity = (self.config.cluster_id, self.config.node_id)
            if observed_identity != expected_identity:
                raise RuntimeError(
                    "Manyfold signer identity does not match Heart configuration "
                    f"(observed={observed_identity!r}, expected={expected_identity!r})"
                )
            status = self._client.ensure_process_credentials(
                max_attempts=self.config.retry_max_attempts,
                retry_delay_seconds=self.config.retry_delay_seconds,
            )
            self._stop.clear()
            thread = threading.Thread(
                target=self._renew_until_closed,
                name="heart-manyfold-credential-renewal",
                daemon=True,
            )
            self._thread = thread
            thread.start()
            self._log_transition(status)
            self._last_status = status
            return status

    def poll(self) -> ProcessCredentialStatus | None:
        """Advance renewal once for health checks and deterministic tests."""
        client = self._client
        if client is None:
            return None
        status = client.credential_status()
        if status.state is not ProcessCredentialState.READY:
            try:
                status = client.ensure_process_credentials(
                    max_attempts=self.config.retry_max_attempts,
                    retry_delay_seconds=self.config.retry_delay_seconds,
                )
            except RuntimeError:
                status = client.credential_status()
        with self._lock:
            self._log_transition(status)
            self._last_status = status
        return status

    def status(self) -> ProcessCredentialStatus | None:
        client = self._client
        return None if client is None else client.credential_status()

    def close(self) -> None:
        """Stop renewal and discard the process credential."""
        with self._lock:
            thread = self._thread
            self._thread = None
            self._stop.set()
        if self._client is not None:
            self._client.close()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)
            if thread.is_alive():
                logger.error("Manyfold credential renewal thread did not stop")

    def _renew_until_closed(self) -> None:
        while not self._stop.wait(self.config.poll_interval_seconds):
            self.poll()

    def _log_transition(self, status: ProcessCredentialStatus) -> None:
        previous = self._last_status
        if (
            previous is not None
            and previous.state is status.state
            and previous.generation == status.generation
        ):
            return
        logger.info(
            "Manyfold process credential state=%s generation=%d expires_at=%s",
            status.state.value,
            status.generation,
            status.expires_at,
        )


def _environment_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ENV_TRUE_VALUES


def _environment_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as error:
        raise ValueError(f"{name} must be numeric") from error


def _environment_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer") from error
