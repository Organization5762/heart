from __future__ import annotations

from datetime import datetime, timezone

from reactivex.subject import Subject

from heart.device.beats.websocket import ControlMessage
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
        self.navigation_profile = _NavigationProfileStub()
        self.external_sensor_hub = _ExternalSensorHubStub()


class _NavigationProfileStub:
    def __init__(self) -> None:
        self.injected: list[tuple[str, int, str]] = []

    def inject_browse(self, step: int, source: str = "beats.control") -> None:
        self.injected.append(("browse", step, source))

    def inject_activate(self, source: str = "beats.control") -> None:
        self.injected.append(("activate", 0, source))

    def inject_alternate_activate(self, source: str = "beats.control") -> None:
        self.injected.append(("alternate_activate", 0, source))


class _ExternalSensorHubStub:
    def __init__(self) -> None:
        self.updates: list[tuple[str, str, float | None]] = []

    def set_value(self, sensor_key: str, value: float) -> None:
        self.updates.append(("set", sensor_key, value))

    def clear_value(self, sensor_key: str) -> None:
        self.updates.append(("clear", sensor_key, None))


class _WebSocketStub:
    def __init__(self) -> None:
        self.sent: list[tuple[str, object]] = []
        self.control_handler = None

    def send(self, kind: str, payload: object) -> None:
        self.sent.append((kind, payload))

    def set_control_handler(self, handler) -> None:
        self.control_handler = handler


class TestPeripheralRuntimeStreaming:
    """Exercise peripheral runtime stream bridging so Beats receives structured reconnect-safe peripheral payloads."""

    def test_configure_streaming_skips_websocket_when_beats_forwarding_is_disabled(
        self, monkeypatch
    ) -> None:
        """Verify default runtime startup avoids booting the Beats websocket so plain sessions do not open an unused server."""

        manager = _PeripheralManagerStub()
        runtime = PeripheralRuntime(manager)  # type: ignore[arg-type]

        monkeypatch.setattr(
            "heart.runtime.peripheral_runtime.Configuration.forward_to_beats_app",
            classmethod(lambda cls: False),
        )

        def _unexpected_websocket() -> object:
            raise AssertionError("WebSocket should not be constructed without Beats forwarding")

        monkeypatch.setattr(
            "heart.runtime.peripheral_runtime._build_websocket",
            _unexpected_websocket,
        )

        runtime.configure_streaming()

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

    def test_configure_streaming_maps_control_commands_into_navigation_injections(
        self,
    ) -> None:
        """Verify websocket control commands inject navigation intents so Beats controls can drive runtime navigation through the shared logical stream."""
        manager = _PeripheralManagerStub()
        runtime = PeripheralRuntime(manager)  # type: ignore[arg-type]
        websocket = _WebSocketStub()

        runtime.configure_streaming(websocket=websocket)  # type: ignore[arg-type]
        assert websocket.control_handler is not None

        websocket.control_handler(ControlMessage(command="browse", browse_step=2))
        websocket.control_handler(ControlMessage(command="activate"))
        websocket.control_handler(ControlMessage(command="alternate_activate"))

        assert manager.navigation_profile.injected == [
            ("browse", 2, "beats.control.browse"),
            ("activate", 0, "beats.control.activate"),
            ("alternate_activate", 0, "beats.control.alternate"),
        ]

    def test_configure_streaming_maps_sensor_control_commands_into_external_hub(
        self,
    ) -> None:
        """Verify websocket sensor commands update the external hub so Beats-side controls become runtime-owned sensor values."""
        manager = _PeripheralManagerStub()
        runtime = PeripheralRuntime(manager)  # type: ignore[arg-type]
        websocket = _WebSocketStub()

        runtime.configure_streaming(websocket=websocket)  # type: ignore[arg-type]
        assert websocket.control_handler is not None

        websocket.control_handler(
            ControlMessage(
                command="sensor_update",
                sensor_key="accelerometer:debug:z",
                sensor_value=12.5,
            )
        )
        websocket.control_handler(
            ControlMessage(
                command="sensor_update",
                sensor_key="accelerometer:debug:z",
                clear=True,
            )
        )

        assert manager.external_sensor_hub.updates == [
            ("set", "accelerometer:debug:z", 12.5),
            ("clear", "accelerometer:debug:z", None),
        ]
