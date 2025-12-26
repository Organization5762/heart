import json
from dataclasses import dataclass
from datetime import datetime, timezone

from heart.device.beats.proto import beats_streaming_pb2
from heart.device.beats.websocket import (_encode_peripheral_message,
                                          decode_stream_envelope)
from heart.peripheral.core import (Input, PeripheralInfo,
                                   PeripheralMessageEnvelope, PeripheralTag)
from heart.peripheral.core.encoding import (PeripheralPayloadEncoding,
                                            decode_peripheral_payload,
                                            encode_peripheral_payload)
from heart.peripheral.proto import input_events_pb2


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
        event = input_events_pb2.InputEvent()
        event.ParseFromString(encoded.payload)
        assert event.event_type == payload.event_type
        assert json.loads(event.data_json.decode("utf-8")) == payload.data


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
