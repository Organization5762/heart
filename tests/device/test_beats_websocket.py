import asyncio
import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from heart.device.beats.proto import beats_streaming_pb2
from heart.device.beats.websocket import (WebSocket,
                                          _encode_peripheral_message,
                                          decode_control_message,
                                          decode_stream_envelope)
from heart.peripheral.core import (Input, PeripheralInfo,
                                   PeripheralMessageEnvelope, PeripheralTag)
from heart.peripheral.core.encoding import (PeripheralPayloadEncoding,
                                            decode_peripheral_payload,
                                            encode_peripheral_payload)
from heart.peripheral.core.protobuf_registry import protobuf_registry
from heart.peripheral.core.protobuf_types import PeripheralPayloadType


class TestPeripheralEnvelopeEncoding:
    """Validate Beats websocket peripheral encoding so clients can decode payloads reliably."""

    def test_encodes_json_payloads_with_default_metadata(self) -> None:
        """Verify JSON payloads are serialized as UTF-8 with no type metadata so existing clients stay compatible."""
        envelope = PeripheralMessageEnvelope(
            peripheral_info=PeripheralInfo(id="peripheral-1"),
            data={"level": 3},
        )

        encoded = _encode_peripheral_message(envelope)

        assert encoded.payload_encoding == beats_streaming_pb2.JSON_UTF8
        assert encoded.payload_type == ""
        assert json.loads(encoded.payload.decode("utf-8")) == {"level": 3}

    def test_encodes_protobuf_payloads_with_message_name(self) -> None:
        """Verify protobuf payloads serialize to bytes with a declared type so typed clients can decode them safely."""
        message = beats_streaming_pb2.Frame(png_data=b"frame-bytes")
        envelope = PeripheralMessageEnvelope(
            peripheral_info=PeripheralInfo(id="peripheral-2"),
            data=message,
        )

        encoded = _encode_peripheral_message(envelope)

        assert encoded.payload_encoding == beats_streaming_pb2.PROTOBUF
        assert encoded.payload_type == "heart.beats.streaming.Frame"
        assert encoded.payload == message.SerializeToString()


class TestPeripheralPayloadEncoding:
    """Ensure the shared peripheral payload encoder emits metadata for protobuf-aware clients."""

    @dataclass(frozen=True)
    class ExamplePayload:
        level: int

    def test_encodes_dataclass_payloads_as_json(self) -> None:
        """Verify dataclass payloads serialize to JSON so non-protobuf sources stay compatible."""
        encoded = encode_peripheral_payload(self.ExamplePayload(level=7))

        assert encoded.encoding == PeripheralPayloadEncoding.JSON_UTF8
        assert encoded.payload_type == ""
        assert json.loads(encoded.payload.decode("utf-8")) == {"level": 7}

    def test_encodes_protobuf_payloads_with_type_name(self) -> None:
        """Verify protobuf payloads include a type name so clients can decode them safely."""
        message = beats_streaming_pb2.Frame(png_data=b"frame-bytes")

        encoded = encode_peripheral_payload(message)

        assert encoded.encoding == PeripheralPayloadEncoding.PROTOBUF
        assert encoded.payload_type == "heart.beats.streaming.Frame"
        assert encoded.payload == message.SerializeToString()


class TestInputPayloadEncoding:
    """Validate Input payload protobuf encoding so event streams stay binary-friendly."""

    def test_encodes_input_payloads_as_protobuf(self) -> None:
        """Verify Input payloads serialize to protobuf so event data stays structured for clients."""
        payload = Input(
            event_type="peripheral.switch.tick",
            data={"rotation": 3, "button": 1},
        )

        encoded = encode_peripheral_payload(payload)

        assert encoded.encoding == PeripheralPayloadEncoding.PROTOBUF
        assert encoded.payload_type == "heart.peripheral.input.InputEvent"
        message_class = protobuf_registry.get_message_class(
            PeripheralPayloadType.INPUT_EVENT
        )
        assert message_class is not None
        event = message_class()
        event.ParseFromString(encoded.payload)
        assert event.event_type == payload.event_type
        assert json.loads(event.data_json.decode("utf-8")) == payload.data

    def test_encodes_input_payloads_with_frozensets(self) -> None:
        """Verify Input payloads normalize frozensets into JSON arrays so websocket streaming does not crash on immutable input snapshots."""
        payload = Input(
            event_type="peripheral.keyboard.snapshot",
            data={"pressed_keys": frozenset({3, 1, 2})},
        )

        encoded = encode_peripheral_payload(payload)

        assert encoded.encoding == PeripheralPayloadEncoding.PROTOBUF
        message_class = protobuf_registry.get_message_class(
            PeripheralPayloadType.INPUT_EVENT
        )
        assert message_class is not None
        event = message_class()
        event.ParseFromString(encoded.payload)
        assert json.loads(event.data_json.decode("utf-8")) == {
            "pressed_keys": [1, 2, 3]
        }


class TestPeripheralPayloadDecoding:
    """Validate protobuf-aware payload decoding so inbound streams round-trip correctly."""

    def test_decodes_json_payloads(self) -> None:
        """Verify JSON payloads decode to native mappings so peripheral data stays usable."""
        encoded = encode_peripheral_payload({"level": 9})

        decoded = decode_peripheral_payload(
            encoded.payload,
            encoding=encoded.encoding,
            payload_type=encoded.payload_type,
        )

        assert decoded == {"level": 9}

    def test_decodes_protobuf_payloads(self) -> None:
        """Verify protobuf payloads decode into messages so typed events remain structured."""
        message = beats_streaming_pb2.Frame(png_data=b"frame-bytes")
        encoded = encode_peripheral_payload(message)

        decoded = decode_peripheral_payload(
            encoded.payload,
            encoding=encoded.encoding,
            payload_type=encoded.payload_type,
        )

        assert isinstance(decoded, beats_streaming_pb2.Frame)
        assert decoded == message

    def test_decodes_input_payloads_into_inputs(self) -> None:
        """Verify Input protobuf payloads decode into Input instances so event routing stays consistent."""
        timestamp = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        payload = Input(
            event_type="peripheral.switch.tick",
            data={"rotation": 1},
            timestamp=timestamp,
        )
        encoded = encode_peripheral_payload(payload)

        decoded = decode_peripheral_payload(
            encoded.payload,
            encoding=encoded.encoding,
            payload_type=encoded.payload_type,
        )

        assert isinstance(decoded, Input)
        assert decoded.event_type == payload.event_type
        assert decoded.data == payload.data
        assert decoded.timestamp == payload.timestamp


class TestStreamEnvelopeDecoding:
    """Exercise websocket stream decoding so protobuf envelopes can be consumed in Python."""

    def test_decodes_frame_envelopes(self) -> None:
        """Verify frame envelopes decode to raw bytes so render streams are portable."""
        envelope = beats_streaming_pb2.StreamEnvelope(
            frame=beats_streaming_pb2.Frame(png_data=b"frame-bytes")
        )

        decoded = decode_stream_envelope(envelope.SerializeToString())

        assert decoded == ("frame", b"frame-bytes")

    def test_decodes_peripheral_envelopes_with_protobuf_payloads(self) -> None:
        """Verify peripheral envelopes decode to typed messages so clients can interpret payloads."""
        message = beats_streaming_pb2.Frame(png_data=b"frame-bytes")
        source = PeripheralMessageEnvelope(
            peripheral_info=PeripheralInfo(
                id="peripheral-3",
                tags=[
                    PeripheralTag(
                        name="input_variant",
                        variant="button",
                        metadata={"version": "v1"},
                    )
                ],
            ),
            data=message,
        )

        peripheral_envelope = _encode_peripheral_message(source)
        envelope = beats_streaming_pb2.StreamEnvelope(peripheral=peripheral_envelope)

        decoded = decode_stream_envelope(envelope.SerializeToString())

        assert decoded is not None
        kind, payload = decoded
        assert kind == "peripheral"
        assert isinstance(payload, PeripheralMessageEnvelope)
        assert payload.peripheral_info == source.peripheral_info
        assert isinstance(payload.data, beats_streaming_pb2.Frame)
        assert payload.data == message


class TestControlMessageDecoding:
    """Validate control-message parsing so Beats can send runtime commands over the websocket."""

    def test_decodes_browse_control_messages(self) -> None:
        """Verify JSON control envelopes decode into browse commands so panel navigation can reach Heart."""
        decoded = decode_control_message(
            json.dumps(
                {
                    "kind": "control",
                    "command": "browse",
                    "browse_step": -1,
                }
            )
        )

        assert decoded is not None
        assert decoded.command == "browse"
        assert decoded.browse_step == -1

    def test_rejects_unknown_control_messages(self) -> None:
        """Verify malformed or unsupported control payloads are ignored so random websocket traffic does not trigger navigation."""
        assert decode_control_message('{"kind":"control","command":"bogus"}') is None

    def test_decodes_sensor_update_control_messages(self) -> None:
        """Verify sensor control payloads decode into keyed numeric updates so Beats can stream external sensor values into Heart."""
        decoded = decode_control_message(
            json.dumps(
                {
                    "kind": "control",
                    "command": "sensor_update",
                    "sensor_key": "accelerometer:debug:z",
                    "sensor_value": 12.5,
                }
            )
        )

        assert decoded is not None
        assert decoded.command == "sensor_update"
        assert decoded.sensor_key == "accelerometer:debug:z"
        assert decoded.sensor_value == 12.5
        assert decoded.clear is False


class TestWebSocketReplayCache:
    """Verify replay caching so reconnecting Beats clients immediately recover current stream state."""

    def test_replays_latest_frame_and_latest_peripheral_state(self) -> None:
        """Verify replay keeps the newest frame and newest payload per peripheral so reconnects recover without waiting for fresh traffic."""
        websocket = object.__new__(WebSocket)
        websocket._replay_lock = threading.Lock()
        websocket._latest_frame = None
        websocket._latest_peripheral_frames = {}

        websocket._cache_replay_frame(
            kind="frame",
            payload=b"old-frame",
            frame_bytes=b"old-frame",
        )
        websocket._cache_replay_frame(
            kind="frame",
            payload=b"latest-frame",
            frame_bytes=b"latest-frame",
        )
        websocket._cache_replay_frame(
            kind="peripheral",
            payload=PeripheralMessageEnvelope(
                peripheral_info=PeripheralInfo(id="switch-1"),
                data={"pressed": False},
            ),
            frame_bytes=b"switch-1-old",
        )
        websocket._cache_replay_frame(
            kind="peripheral",
            payload=PeripheralMessageEnvelope(
                peripheral_info=PeripheralInfo(id="switch-1"),
                data={"pressed": True},
            ),
            frame_bytes=b"switch-1-latest",
        )
        websocket._cache_replay_frame(
            kind="peripheral",
            payload=PeripheralMessageEnvelope(
                peripheral_info=PeripheralInfo(id="sensor-1"),
                data={"x": 1},
            ),
            frame_bytes=b"sensor-1-latest",
        )

        assert websocket._replay_frames() == (
            b"latest-frame",
            b"switch-1-latest",
            b"sensor-1-latest",
        )


class TestWebSocketDisconnectHandling:
    """Validate disconnect handling so expected client drops do not surface as server errors."""

    def test_handler_ignores_disconnect_during_replay_send(self) -> None:
        """Verify replay send disconnects are treated as normal closure so reconnect churn does not log handler failures."""
        from websockets.exceptions import ConnectionClosedError

        websocket = object.__new__(WebSocket)
        websocket.clients = set()
        websocket._replay_lock = threading.Lock()
        websocket._latest_frame = b"replay-frame"
        websocket._latest_peripheral_frames = {}

        class _ClosingConnection:
            async def send(self, _frame: bytes) -> None:
                raise ConnectionClosedError(
                    None,
                    None,
                )

            async def wait_closed(self) -> None:
                raise AssertionError("wait_closed should not run after replay disconnect")

        connection = _ClosingConnection()
        asyncio.run(websocket._handle_client(connection))
        assert connection not in websocket.clients

    def test_handler_dispatches_control_messages(self) -> None:
        """Verify client websocket messages reach the registered control handler so Beats can drive navigation remotely."""
        websocket = object.__new__(WebSocket)
        websocket.clients = set()
        websocket._replay_lock = threading.Lock()
        websocket._latest_frame = None
        websocket._latest_peripheral_frames = {}
        received = []
        websocket._control_handler = received.append

        class _Connection:
            def __aiter__(self):
                async def iterator():
                    yield json.dumps(
                        {
                            "kind": "control",
                            "command": "activate",
                        }
                    )

                return iterator()

            async def send(self, _frame: bytes) -> None:
                return None

        asyncio.run(websocket._handle_client(_Connection()))

        assert [message.command for message in received] == ["activate"]
