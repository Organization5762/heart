from __future__ import annotations

from datetime import datetime, timezone

from heart.device.beats.websocket import ControlMessage
from heart.peripheral.core.input import InputDebugStage, InputDebugTap
from heart.runtime.peripheral_runtime import (INPUT_DEBUG_STAGE_TAG,
                                              INPUT_DEBUG_STREAM_TAG,
                                              PeripheralRuntime)


class _PeripheralManagerStub:
    def __init__(self) -> None:
        self.input_io = _InputIOStub()


class _InputIOStub:
    def __init__(self) -> None:
        self.debug_tap = InputDebugTap()
        self.navigation = _NavigationProfileStub()
        self.external_sensors = _ExternalSensorHubStub()


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


class _TemporaryRendererLoop:
    def __init__(self) -> None:
        self.clear_count = 0

    def clear_temporary_renderer(self) -> None:
        self.clear_count += 1


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
            raise AssertionError(
                "WebSocket should not be constructed without Beats forwarding"
            )

        monkeypatch.setattr(
            "heart.runtime.peripheral_runtime._build_websocket",
            _unexpected_websocket,
        )

        runtime.configure_streaming()

    def test_configure_streaming_emits_peripheral_envelopes(self, monkeypatch) -> None:
        """Verify debug tap events are wrapped as peripheral payloads so the Beats websocket can replay and decode them after reconnects."""
        manager = _PeripheralManagerStub()
        runtime = PeripheralRuntime(manager)  # type: ignore[arg-type]
        websocket = _WebSocketStub()

        monkeypatch.setattr(
            "heart.runtime.peripheral_runtime.Configuration.stream_beats_input_debug",
            classmethod(lambda cls: True),
        )

        runtime.configure_streaming(websocket=websocket)  # type: ignore[arg-type]
        manager.input_io.debug_tap.publish(
            stage=InputDebugStage.RAW,
            stream_name="switch.tick",
            source_id="switch-1",
            payload={
                "rotation": 1,
                "timestamp": datetime(2024, 1, 1, tzinfo=timezone.utc),
            },
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

    def test_configure_streaming_leaves_input_debug_off_by_default(self) -> None:
        """Keep Beats frame/control streaming lightweight unless debug telemetry is explicitly requested."""
        manager = _PeripheralManagerStub()
        runtime = PeripheralRuntime(manager)  # type: ignore[arg-type]
        websocket = _WebSocketStub()

        runtime.configure_streaming(websocket=websocket)  # type: ignore[arg-type]
        manager.input_io.debug_tap.publish(
            stage=InputDebugStage.RAW,
            stream_name="switch.tick",
            source_id="switch-1",
            payload={"rotation": 1},
        )

        assert websocket.control_handler is not None
        assert websocket.sent == []

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

        assert manager.input_io.navigation.injected == []
        runtime._drain_control_messages()

        assert manager.input_io.navigation.injected == [
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

        assert manager.input_io.external_sensors.updates == []
        runtime._drain_control_messages()

        assert manager.input_io.external_sensors.updates == [
            ("set", "accelerometer:debug:z", 12.5),
            ("clear", "accelerometer:debug:z", None),
        ]

    def test_image_clear_control_clears_temporary_renderer(self, monkeypatch) -> None:
        """Verify image clear controls remove a transient phone image instead of leaving stale artwork on screen."""
        manager = _PeripheralManagerStub()
        runtime = PeripheralRuntime(manager)  # type: ignore[arg-type]
        websocket = _WebSocketStub()
        loop = _TemporaryRendererLoop()
        monkeypatch.setattr(
            "heart.runtime.peripheral_runtime.get_active_game_loop",
            lambda: loop,
        )

        runtime.configure_streaming(websocket=websocket)  # type: ignore[arg-type]
        assert websocket.control_handler is not None

        websocket.control_handler(ControlMessage(command="image_update", clear=True))
        runtime._drain_control_messages()

        assert loop.clear_count == 1
