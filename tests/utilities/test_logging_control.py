import logging

import pytest

from heart.utilities import logging_control


class StubLogger:
    def __init__(self) -> None:
        self.records: list[tuple[int, str, tuple[object, ...], dict[str, object] | None]] = []

    def log(
        self,
        level: int,
        msg: str,
        *args: object,
        extra: dict[str, object] | None = None,
    ) -> None:
        self.records.append((level, msg, tuple(args), extra))


def test_logging_controller_applies_interval() -> None:
    """Verify per-key intervals throttle logs to limit noisy repeats for stability."""
    monotonic_values = [0.0]

    def monotonic() -> float:
        return monotonic_values[0]

    controller = logging_control.LoggingController(
        default_interval=1.0,
        default_fallback_level=logging.DEBUG,
        rules={},
        monotonic=monotonic,
    )

    logger = StubLogger()

    emitted = controller.log(
        key="render.loop",
        logger=logger,
        level=logging.INFO,
        msg="render.loop",
        args=("primary",),
        fallback_level=logging.DEBUG,
    )

    assert emitted is True
    assert logger.records[-1][0] == logging.INFO

    emitted = controller.log(
        key="render.loop",
        logger=logger,
        level=logging.INFO,
        msg="render.loop",
        args=("secondary",),
        fallback_level=logging.DEBUG,
    )

    assert emitted is False
    assert logger.records[-1][0] == logging.DEBUG

    monotonic_values[0] = 1.0
    emitted = controller.log(
        key="render.loop",
        logger=logger,
        level=logging.INFO,
        msg="render.loop",
        args=("tertiary",),
        fallback_level=logging.DEBUG,
    )

    assert emitted is True
    assert logger.records[-1][0] == logging.INFO


@pytest.fixture(autouse=True)
def reset_logging_controller_cache() -> None:
    logging_control.get_logging_controller.cache_clear()  # type: ignore[attr-defined]
    yield
    logging_control.get_logging_controller.cache_clear()  # type: ignore[attr-defined]


def test_logging_controller_respects_rule_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Confirm rule overrides adjust fallback levels so operators can tune alerting."""
    monkeypatch.setenv("HEART_LOG_RULES", "render.loop=none:WARNING:none")
    controller = logging_control.get_logging_controller()

    logger = StubLogger()

    emitted = controller.log(
        key="render.loop",
        logger=logger,
        level=logging.INFO,
        msg="render.loop",
        args=(),
        fallback_level=logging.DEBUG,
    )

    assert emitted is True
    assert logger.records[-1][0] == logging.WARNING

    emitted = controller.log(
        key="render.loop",
        logger=logger,
        level=logging.INFO,
        msg="render.loop",
        args=(),
        fallback_level=logging.DEBUG,
    )

    assert emitted is True
    assert len(logger.records) == 2
    assert logger.records[-1][0] == logging.WARNING
