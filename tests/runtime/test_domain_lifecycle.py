from __future__ import annotations

from contextlib import nullcontext
from unittest.mock import Mock

import numpy as np
import pytest

from heart.navigation import MultiScene
from heart.peripheral.core.input.debug import InputDebugTap
from heart.peripheral.core.input.external_sensors import ExternalSensorHub
from heart.peripheral.core.input.profiles.navigation import ActivateIntent
from heart.peripheral.microphone import Microphone
from heart.renderers import StatefulBaseRenderer
from heart.runtime.domain_lifecycle import (HeartLifecycleKind,
                                            HeartLifecycleReason,
                                            pipeline_lifecycle_topic,
                                            renderer_lifecycle_topic,
                                            scene_lifecycle_topic,
                                            sensor_lifecycle_topic)
from heart.runtime.game_loop import GameLoop


class _Subscription:
    def dispose(self) -> None:
        return None


class _Navigation:
    def __init__(self) -> None:
        self.on_activate = None

    def subscribe_events(self, *, on_activate, **_kwargs):
        self.on_activate = on_activate
        return _Subscription()


class _PeripheralManager:
    def __init__(self) -> None:
        self.input_io = Mock()
        self.input_io.navigation = _Navigation()
        self.input_io.controls.gamepads.return_value = ()


class _Scene(StatefulBaseRenderer[int]):
    def __init__(self, name: str) -> None:
        self._scene_name = name
        super().__init__()

    @property
    def name(self) -> str:
        return self._scene_name

    def _create_initial_state(self, *_args, **_kwargs) -> int:
        return 0

    def real_process(self, *_args, **_kwargs) -> None:
        return None


class _FailingRenderer(StatefulBaseRenderer[int]):
    def __init__(self) -> None:
        self.should_fail = False
        super().__init__(state=0)

    def real_process(self, *_args, **_kwargs) -> None:
        if self.should_fail:
            raise RuntimeError("render failed")


def test_scene_transition_sequence_matches_visible_selection() -> None:
    observed = []
    subscription = scene_lifecycle_topic().subscribe(observed.append)
    manager = _PeripheralManager()
    first = _Scene("first")
    second = _Scene("second")
    scenes = MultiScene([first, second])
    window = Mock()
    window.screen = None
    window.display_mode.side_effect = lambda _mode: nullcontext(window)
    try:
        scenes.initialize(window, manager, Mock())
        manager.input_io.navigation.on_activate(
            ActivateIntent(source="test", request_id="navigate-1")
        )
    finally:
        subscription.dispose()

    correlated = [
        event
        for event in observed
        if event.correlation_id == "navigate-1"
    ]
    assert [event.kind for event in correlated] == [
        HeartLifecycleKind.SCENE_SELECTED.value,
        HeartLifecycleKind.SCENE_DEACTIVATED.value,
        HeartLifecycleKind.SCENE_ACTIVATED.value,
    ]
    assert [renderer.name for renderer in scenes.get_renderers()] == ["second"]


def test_sensor_transitions_online_stale_offline_and_clears_value() -> None:
    now = [10.0]
    observed = []
    subscription = sensor_lifecycle_topic().subscribe(observed.append)
    hub = ExternalSensorHub(
        InputDebugTap(0, 0),
        monotonic=lambda: now[0],
    )
    acceleration = []
    acceleration_subscription = hub.observable_acceleration().subscribe(
        acceleration.append
    )
    try:
        hub.set_value("accelerometer:test:x", 2.0)
        now[0] = 12.1
        hub.poll()
        now[0] = 14.1
        hub.poll()
    finally:
        acceleration_subscription.dispose()
        hub.close()
        subscription.dispose()

    matching = [
        event
        for event in observed
        if event.entity_id == "accelerometer:test:x"
    ]
    assert [event.kind for event in matching] == [
        HeartLifecycleKind.SENSOR_ONLINE.value,
        HeartLifecycleKind.SENSOR_STALE.value,
        HeartLifecycleKind.SENSOR_OFFLINE.value,
    ]
    assert [event.reason for event in matching[1:]] == [
        HeartLifecycleReason.TTL_EXPIRED.value,
        HeartLifecycleReason.TTL_EXPIRED.value,
    ]
    assert hub.sensor_status("accelerometer:test:x") == "offline"
    assert acceleration[-1] is None


def test_renderer_failure_recovery_and_stop_are_transition_bounded() -> None:
    observed = []
    subscription = renderer_lifecycle_topic().subscribe(observed.append)
    renderer = _FailingRenderer()
    renderer.should_fail = True
    try:
        with pytest.raises(RuntimeError, match="render failed"):
            renderer._internal_process(Mock(), Mock(), Mock())
        with pytest.raises(RuntimeError, match="render failed"):
            renderer._internal_process(Mock(), Mock(), Mock())
        renderer.should_fail = False
        renderer._internal_process(Mock(), Mock(), Mock())
        renderer.reset()
    finally:
        subscription.dispose()

    matching = [
        event for event in observed if event.entity_id == "_FailingRenderer"
    ]
    assert [event.kind for event in matching] == [
        HeartLifecycleKind.RENDERER_STARTED.value,
        HeartLifecycleKind.RENDERER_FAILED.value,
        HeartLifecycleKind.RENDERER_STARTED.value,
        HeartLifecycleKind.RENDERER_STOPPED.value,
    ]
    assert matching[2].reason == HeartLifecycleReason.RECOVERED.value


def test_frame_pressure_and_recovery_emit_only_on_threshold_transitions(
    device,
    resolver,
) -> None:
    observed = []
    subscription = pipeline_lifecycle_topic().subscribe(observed.append)
    loop = GameLoop(device=device, resolver=resolver, max_fps=100)
    try:
        loop._observe_frame_pipeline_pressure(
            {"total_ms": 15.0, "pacing_ms": 0.0}
        )
        loop._observe_frame_pipeline_pressure(
            {"total_ms": 20.0, "pacing_ms": 0.0}
        )
        loop._observe_frame_pipeline_pressure(
            {"total_ms": 9.0, "pacing_ms": 0.0}
        )
    finally:
        subscription.dispose()

    matching = [
        event for event in observed if event.entity_id == "game-loop"
    ]
    assert [event.kind for event in matching] == [
        HeartLifecycleKind.FRAME_PIPELINE_PRESSURE.value,
        HeartLifecycleKind.FRAME_PIPELINE_RECOVERED.value,
    ]


def test_audio_pressure_and_recovery_coalesce_repeated_status_blocks() -> None:
    observed = []
    subscription = pipeline_lifecycle_topic().subscribe(observed.append)
    microphone = Microphone()
    audio = np.zeros((4, 1), dtype=np.float32)
    try:
        microphone._handle_audio_block(audio, 4, None, "overflow")
        microphone._handle_audio_block(audio, 4, None, "overflow")
        microphone._handle_audio_block(audio, 4, None, None)
    finally:
        subscription.dispose()

    matching = [
        event for event in observed if event.entity_id == "microphone:default"
    ]
    assert [event.kind for event in matching] == [
        HeartLifecycleKind.AUDIO_PIPELINE_PRESSURE.value,
        HeartLifecycleKind.AUDIO_PIPELINE_RECOVERED.value,
    ]
