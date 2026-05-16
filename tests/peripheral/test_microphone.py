from __future__ import annotations

from typing import Any

import numpy as np
from manyfold import Graph

from heart.peripheral import microphone
from heart.peripheral.microphone import (Microphone,
                                         microphone_detection_route,
                                         microphone_level_event_route)


class _InputStreamStub:
    def __init__(self, *, callback: Any, blocks: tuple[np.ndarray, ...]) -> None:
        self._callback = callback
        self._blocks = blocks

    def __enter__(self) -> "_InputStreamStub":
        for block in self._blocks:
            self._callback(block, len(block), None, None)
        return self

    def __exit__(self, *args: Any) -> None:
        return None


class _SoundDeviceStub:
    def __init__(self, *, blocks: tuple[np.ndarray, ...] = ()) -> None:
        self._blocks = blocks

    def query_devices(self) -> list[dict[str, int]]:
        return [{"max_input_channels": 1}]

    def InputStream(self, **kwargs: Any) -> _InputStreamStub:
        return _InputStreamStub(
            callback=kwargs["callback"],
            blocks=self._blocks,
        )


class TestPeripheralMicrophone:
    """Group Peripheral Microphone tests so peripheral microphone behaviour stays reliable. This preserves confidence in peripheral microphone for end-to-end scenarios."""

    def test_detect_without_sounddevice(self, monkeypatch):
        """Verify detect short-circuits without sounddevice so deployments degrade gracefully."""

        monkeypatch.setattr(microphone, "sd", None)
        assert list(Microphone.detect()) == []

    def test_detection_node_publishes_microphone_to_manyfold_route(
        self,
        monkeypatch,
    ) -> None:
        monkeypatch.setattr(microphone, "sd", _SoundDeviceStub())
        graph = Graph()
        registered: list[Microphone] = []

        handle = Microphone.detection_node(
            start_immediately=False,
            on_detect=lambda peripheral, _access: registered.append(peripheral),
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest_detection = graph.latest(microphone_detection_route())
        assert len(registered) == 1
        assert latest_detection is not None
        assert latest_detection.value.event_type == "peripheral.microphone.detected"
        assert latest_detection.value.data["samplerate"] == 16_000

    def test_detection_node_can_spawn_level_source(self, monkeypatch) -> None:
        block = np.array([[0.0], [0.5], [-1.0]], dtype=float)
        monkeypatch.setattr(microphone, "sd", _SoundDeviceStub(blocks=(block,)))
        graph = Graph()

        handle = Microphone.detection_node(
            start_immediately=False,
            spawn_sources=True,
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)
        assert len(handle.spawned_handles) == 1

        spawned = handle.spawned_handles[0]
        spawned.loop_handle.token.set()
        spawned.loop_handle.loop.run(spawned.loop_handle.token)

        latest_level = graph.latest(microphone_level_event_route())
        assert latest_level is not None
        assert latest_level.value.event_type == "peripheral.microphone.level"
        assert latest_level.value.data["frames"] == 3
        assert latest_level.value.data["samplerate"] == 16_000
