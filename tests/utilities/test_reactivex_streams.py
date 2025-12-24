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
            ("replay_latest", [2]),
            ("replay_latest_auto_connect", [2]),
        ],
        ids=[
            "share_no_replay",
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

    def test_share_stream_auto_connect_avoids_resubscribe(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify auto-connect keeps a single subscription to reduce churn and preserve hot stream state."""

        monkeypatch.setenv(
            "HEART_RX_STREAM_SHARE_STRATEGY", "replay_latest_auto_connect"
        )
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
        assert received_b == [1]

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
