"""Validate Rx threading helpers so scheduler isolation stays measurable and pygame-bound delivery stays correct."""

from __future__ import annotations

import threading

import pytest

import heart.utilities.reactive as reactive
from heart.utilities.reactive import Disposable
from heart.utilities.reactive_threads import (
    FRAME_THREAD_LATENCY_STREAM, background_scheduler, blocking_io_scheduler,
    delivery_latency_snapshot, drain_frame_thread_queue, input_scheduler,
    on_frame_thread, pipe_in_main_thread,
    reset_reactive_threading_state_for_tests, scheduler_diagnostics)


@pytest.fixture(autouse=True)
def _reset_reactive_threads() -> None:
    reset_reactive_threading_state_for_tests()
    yield
    reset_reactive_threading_state_for_tests()


class TestFrameThreadHandoff:
    """Group frame-thread tests so pygame-affine work only executes when the game loop drains the queue."""

    def test_pipe_in_main_thread_defers_delivery_until_frame_drain(self) -> None:
        """Verify frame-thread delivery waits for an explicit drain and then runs on the draining thread so pygame observers keep thread affinity."""
        source: reactive.Subject[int] = reactive.Subject()
        observed: list[tuple[int, int]] = []

        pipe_in_main_thread(
            source,
            reactive.operators.map(lambda value: (value, threading.get_ident())),
        ).subscribe(observed.append)

        thread = threading.Thread(
            name="test-rx-emitter",
            target=lambda: source.on_next(7),
            daemon=True,
        )
        thread.start()
        thread.join()

        assert observed == []

        drain_frame_thread_queue()

        assert observed == [(7, threading.get_ident())]
        assert on_frame_thread()
        assert delivery_latency_snapshot()[FRAME_THREAD_LATENCY_STREAM].count >= 1


class TestSchedulerIsolation:
    """Group scheduler-isolation tests so slow blocking readers cannot starve latency-sensitive input work."""

    def test_blocking_io_scheduler_does_not_delay_input_scheduler(self) -> None:
        """Verify a blocked IO source leaves input scheduling responsive so keyboard and switch delivery stay predictable under peripheral stalls."""
        started = threading.Event()
        release = threading.Event()
        input_ready = threading.Event()
        blocking_values: list[str] = []
        input_values: list[str] = []

        def _blocking_source(observer, _scheduler=None):
            started.set()
            release.wait(timeout=1.0)
            observer.on_next("blocking")
            observer.on_completed()
            return Disposable()

        reactive.create(_blocking_source).pipe(
            reactive.operators.subscribe_on(blocking_io_scheduler()),
        ).subscribe(blocking_values.append)

        assert started.wait(timeout=0.5)

        reactive.just("input").pipe(
            reactive.operators.subscribe_on(input_scheduler()),
        ).subscribe(
            on_next=input_values.append,
            on_completed=input_ready.set,
        )

        assert input_ready.wait(timeout=0.5)
        assert input_values == ["input"]
        assert blocking_values == []

        release.set()

    def test_scheduler_diagnostics_reflect_configured_worker_counts(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify scheduler diagnostics expose configured worker counts so scheduler tuning changes are observable in tests and runtime diagnostics."""
        monkeypatch.setenv("HEART_RX_BACKGROUND_MAX_WORKERS", "6")
        monkeypatch.setenv("HEART_RX_BLOCKING_IO_MAX_WORKERS", "3")
        monkeypatch.setenv("HEART_RX_INPUT_MAX_WORKERS", "5")

        background_scheduler()
        blocking_io_scheduler()
        input_scheduler()

        assert scheduler_diagnostics() == {
            "background_max_workers": 6,
            "blocking_io_max_workers": 3,
            "input_max_workers": 5,
        }
