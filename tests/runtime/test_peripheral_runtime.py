from __future__ import annotations

from datetime import datetime, timezone

from reactivex.subject import Subject

from heart.peripheral.core.input import InputDebugEnvelope, InputDebugStage
from heart.runtime.peripheral_runtime import (INPUT_DEBUG_STAGE_TAG,
                                              INPUT_DEBUG_STREAM_TAG,
                                              PeripheralRuntime)


class _DebugTapStub:
    def __init__(self) -> None:
        self.subject: Subject[InputDebugEnvelope] = Subject()

    def observable(self) -> Subject[InputDebugEnvelope]:
        return self.subject


class _PeripheralManagerStub:
    def __init__(self) -> None:
        self.debug_tap = _DebugTapStub()


class _WebSocketStub:
    def __init__(self) -> None:
        self.sent: list[tuple[str, object]] = []

    def send(self, kind: str, payload: object) -> None:
        self.sent.append((kind, payload))


class TestPeripheralRuntimeStreaming:
    """Exercise peripheral runtime stream bridging so Beats receives structured reconnect-safe peripheral payloads."""

    def test_configure_streaming_emits_peripheral_envelopes(self) -> None:
        """Verify debug tap events are wrapped as peripheral payloads so the Beats websocket can replay and decode them after reconnects."""
        manager = _PeripheralManagerStub()
        runtime = PeripheralRuntime(manager)  # type: ignore[arg-type]
        websocket = _WebSocketStub()

        runtime.configure_streaming(websocket=websocket)  # type: ignore[arg-type]
        manager.debug_tap.subject.on_next(
            InputDebugEnvelope(
                stage=InputDebugStage.RAW,
                stream_name="switch.tick",
                source_id="switch-1",
                timestamp_monotonic=12.5,
                payload={
                    "rotation": 1,
                    "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
                },
            )
        )

        assert len(websocket.sent) == 1
        kind, envelope = websocket.sent[0]
        assert kind == "peripheral"
        assert envelope.peripheral_info.id == "switch-1"
        assert envelope.peripheral_info.tags[0].name == INPUT_DEBUG_STAGE_TAG
        assert envelope.peripheral_info.tags[0].variant == InputDebugStage.RAW.value
        assert envelope.peripheral_info.tags[1].name == INPUT_DEBUG_STREAM_TAG
        assert envelope.peripheral_info.tags[1].variant == "switch.tick"
        assert envelope.data["stream_name"] == "switch.tick"
        assert envelope.data["source_id"] == "switch-1"
