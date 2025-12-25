import time
from types import SimpleNamespace

import pytest
import reactivex
from reactivex.disposable import Disposable
from reactivex.subject import Subject

from heart.utilities.reactivex_streams import share_stream


class TestShareStreamStrategy:
    """Validate reactive stream sharing strategies for core event pipelines."""

    @pytest.mark.parametrize(
        ("strategy", "expected_initial"),
        [
            ("share", []),
            ("share_auto_connect", []),
            ("replay_latest", [2]),
            ("replay_latest_auto_connect", [2]),
        ],
        ids=[
            "share_no_replay",
            "share_auto_connect_no_replay",
            "replay_latest_replays_last",
            "replay_latest_auto_connect_replays_last",
        ],
    )
    def test_share_stream_replays_latest_when_configured(
        self,
        monkeypatch: pytest.MonkeyPatch,
        strategy: str,
        expected_initial: list[int],
    ) -> None:
        """Ensure configured replay behaviour matches expectations to preserve late-subscriber correctness."""

        monkeypatch.setenv("HEART_RX_STREAM_SHARE_STRATEGY", strategy)
        source: Subject[int] = Subject()
        shared = share_stream(source, stream_name="test")

        received_a: list[int] = []
        shared.subscribe(received_a.append)

        source.on_next(1)
        source.on_next(2)

        received_b: list[int] = []
        shared.subscribe(received_b.append)

        assert received_b == expected_initial

        source.on_next(3)

        assert received_a == [1, 2, 3]
        assert received_b == [*expected_initial, 3]

    @pytest.mark.parametrize(
        ("strategy", "expected_second_subscriber"),
        [
            ("replay_latest_auto_connect", [1]),
            ("share_auto_connect", []),
        ],
        ids=["replay_latest_auto_connect_replays", "share_auto_connect_no_replay"],
    )
    def test_share_stream_auto_connect_avoids_resubscribe(
        self,
        monkeypatch: pytest.MonkeyPatch,
        strategy: str,
        expected_second_subscriber: list[int],
    ) -> None:
        """Verify auto-connect keeps a single subscription to reduce churn and preserve hot stream state."""

        monkeypatch.setenv("HEART_RX_STREAM_SHARE_STRATEGY", strategy)
        subscribe_count = 0

        def _subscribe(observer, scheduler=None):
            nonlocal subscribe_count
            subscribe_count += 1
            observer.on_next(subscribe_count)
            return Disposable()

        source = reactivex.create(_subscribe)
        shared = share_stream(source, stream_name="auto_connect")

        received_a: list[int] = []
        subscription = shared.subscribe(received_a.append)
        subscription.dispose()

        received_b: list[int] = []
        shared.subscribe(received_b.append)

        assert subscribe_count == 1
        assert received_a == [1]
        assert received_b == expected_second_subscriber

    def test_share_stream_replays_buffer_when_configured(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Confirm replay buffer sizing keeps recent context available for observability and recovery."""

        monkeypatch.setenv("HEART_RX_STREAM_SHARE_STRATEGY", "replay_buffer")
        monkeypatch.setenv("HEART_RX_STREAM_REPLAY_BUFFER", "2")
        source: Subject[int] = Subject()
        shared = share_stream(source, stream_name="buffered")

        received_a: list[int] = []
        shared.subscribe(received_a.append)

        source.on_next(1)
        source.on_next(2)
        source.on_next(3)

        received_b: list[int] = []
        shared.subscribe(received_b.append)

        assert received_b == [2, 3]
        source.on_next(4)
        assert received_b == [2, 3, 4]

    def test_share_stream_honors_replay_window(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ensure replay windows drop stale events so late subscribers see only fresh context."""

        monkeypatch.setenv("HEART_RX_STREAM_SHARE_STRATEGY", "replay_latest")
        monkeypatch.setenv("HEART_RX_STREAM_REPLAY_WINDOW_MS", "5")
        source: Subject[int] = Subject()
        shared = share_stream(source, stream_name="windowed")

        received_a: list[int] = []
        shared.subscribe(received_a.append)

        source.on_next(1)
        time.sleep(0.02)

        received_b: list[int] = []
        shared.subscribe(received_b.append)

        assert received_b == []

        source.on_next(2)

        assert received_a == [1, 2]
        assert received_b == [2]

    def test_share_stream_auto_connect_respects_min_subscribers(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify auto-connect waits for the configured subscriber count to avoid premature subscriptions."""

        monkeypatch.setenv(
            "HEART_RX_STREAM_SHARE_STRATEGY", "replay_latest_auto_connect"
        )
        monkeypatch.setenv("HEART_RX_STREAM_AUTO_CONNECT_MIN_SUBSCRIBERS", "2")
        subscribe_count = 0

        def _subscribe(observer, scheduler=None):
            nonlocal subscribe_count
            subscribe_count += 1
            observer.on_next(subscribe_count)
            return Disposable()

        source = reactivex.create(_subscribe)
        shared = share_stream(source, stream_name="min_subscribers")

        received_a: list[int] = []
        shared.subscribe(received_a.append)

        assert subscribe_count == 0

        received_b: list[int] = []
        shared.subscribe(received_b.append)

        assert subscribe_count == 1
        assert received_a == [1]
        assert received_b == [1]

    def test_share_stream_refcount_grace_delays_disconnect(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ensure ref-count grace keeps upstream subscriptions alive to reduce churn during subscriber flapping."""

        monkeypatch.setenv("HEART_RX_STREAM_SHARE_STRATEGY", "replay_latest")
        monkeypatch.setenv("HEART_RX_STREAM_REFCOUNT_GRACE_MS", "30")
        subscribe_count = 0

        def _subscribe(observer, scheduler=None):
            nonlocal subscribe_count
            subscribe_count += 1
            observer.on_next(subscribe_count)
            return Disposable()

        source = reactivex.create(_subscribe)
        shared = share_stream(source, stream_name="grace")

        subscription_a = shared.subscribe()
        subscription_a.dispose()

        shared.subscribe().dispose()

        assert subscribe_count == 1

        time.sleep(0.05)

        subscription_c = shared.subscribe()
        subscription_d = shared.subscribe()

        assert subscribe_count == 2

        subscription_c.dispose()
        subscription_d.dispose()

    def test_share_stream_refcount_grace_connects_after_subscribe(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Confirm lazy ref-count connection preserves immediate emissions to protect hot-stream correctness."""

        monkeypatch.setenv("HEART_RX_STREAM_SHARE_STRATEGY", "share")
        monkeypatch.setenv("HEART_RX_STREAM_REFCOUNT_GRACE_MS", "10")
        monkeypatch.setenv("HEART_RX_STREAM_CONNECT_MODE", "lazy")

        def _subscribe(observer, scheduler=None):
            observer.on_next("ready")
            return Disposable()

        source = reactivex.create(_subscribe)
        shared = share_stream(source, stream_name="connect_order")

        received: list[str] = []
        shared.subscribe(received.append)

        assert received == ["ready"]

    def test_share_stream_refcount_min_subscribers_gates_connections(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ensure ref-count min subscribers gates connections to reduce upstream load until demand is sufficient."""

        monkeypatch.setenv("HEART_RX_STREAM_SHARE_STRATEGY", "share")
        monkeypatch.setenv("HEART_RX_STREAM_REFCOUNT_MIN_SUBSCRIBERS", "2")
        monkeypatch.setenv("HEART_RX_STREAM_REFCOUNT_GRACE_MS", "0")
        subscribe_count = 0

        def _subscribe(observer, scheduler=None):
            nonlocal subscribe_count
            subscribe_count += 1
            return Disposable()

        source = reactivex.create(_subscribe)
        shared = share_stream(source, stream_name="min_refcount")

        subscription_a = shared.subscribe()
        assert subscribe_count == 0

        subscription_b = shared.subscribe()
        assert subscribe_count == 1

        subscription_a.dispose()
        subscription_b.dispose()

        subscription_c = shared.subscribe()
        subscription_d = shared.subscribe()

        assert subscribe_count == 2

        subscription_c.dispose()
        subscription_d.dispose()


class TestShareStreamFlowControl:
    """Cover flow-control safeguards that protect reactive streams under high-frequency loads."""

    def test_share_stream_coalesces_latest_when_configured(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ensure coalescing emits the latest payload per window to preserve responsiveness under load."""

        monkeypatch.setenv("HEART_RX_STREAM_SHARE_STRATEGY", "share")
        monkeypatch.setenv("HEART_RX_STREAM_COALESCE_WINDOW_MS", "20")
        source: Subject[int] = Subject()
        shared = share_stream(source, stream_name="coalesce")

        received: list[int] = []
        shared.subscribe(received.append)

        source.on_next(1)
        source.on_next(2)

        time.sleep(0.03)

        source.on_next(3)
        time.sleep(0.03)

        assert received == [2, 3]

    def test_share_stream_flushes_pending_values_on_completion(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify completion flushes pending values so final state updates are not lost."""

        monkeypatch.setenv("HEART_RX_STREAM_SHARE_STRATEGY", "share")
        monkeypatch.setenv("HEART_RX_STREAM_COALESCE_WINDOW_MS", "50")
        source: Subject[int] = Subject()
        shared = share_stream(source, stream_name="coalesce_complete")

        received: list[int] = []
        shared.subscribe(received.append)

        source.on_next(42)
        source.on_completed()

        assert received == [42]

    def test_share_stream_coalesce_flushes_overdue_window(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Confirm overdue coalescing windows flush pending values to avoid delayed updates."""

        from heart.utilities import reactivex_streams

        monkeypatch.setenv("HEART_RX_STREAM_SHARE_STRATEGY", "share")
        monkeypatch.setenv("HEART_RX_STREAM_COALESCE_WINDOW_MS", "5")

        def _schedule_relative(_delay: float, _action):
            return Disposable()

        monkeypatch.setattr(
            reactivex_streams,
            "_COALESCE_SCHEDULER",
            SimpleNamespace(schedule_relative=_schedule_relative),
        )

        source: Subject[int] = Subject()
        shared = share_stream(source, stream_name="coalesce_overdue")

        received: list[int] = []
        shared.subscribe(received.append)

        source.on_next(1)
        time.sleep(0.02)
        source.on_next(2)
        source.on_completed()

        assert received == [1, 2]
