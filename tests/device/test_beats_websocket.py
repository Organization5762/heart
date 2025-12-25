import json
from dataclasses import dataclass

import pytest

from heart.device.beats.proto import beats_streaming_pb2
from heart.device.beats.websocket import _encode_peripheral_message
from heart.peripheral.core import PeripheralInfo, PeripheralMessageEnvelope
from heart.peripheral.core.encoding import (PeripheralPayloadDecodeError,
                                            PeripheralPayloadEncoding,
                                            decode_peripheral_payload,
                                            encode_peripheral_payload)


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


class TestPeripheralPayloadDecoding:
    """Validate payload decoding so receivers can reconstruct peripheral data accurately."""

    def test_decodes_json_payloads_into_mappings(self) -> None:
        """Verify JSON payloads decode to mappings so consumers can inspect fields without protobuf tooling."""
        payload = encode_peripheral_payload({"level": 9})

        decoded = decode_peripheral_payload(payload)

        assert decoded == {"level": 9}

    def test_decodes_protobuf_payloads_into_messages(self) -> None:
        """Verify protobuf payloads decode to message objects so typed data stays intact across transports."""
        message = beats_streaming_pb2.Frame(png_data=b"frame-bytes")
        payload = encode_peripheral_payload(message)

        decoded = decode_peripheral_payload(payload)

        assert isinstance(decoded, beats_streaming_pb2.Frame)
        assert decoded == message

    def test_raises_on_unknown_protobuf_type(self) -> None:
        """Verify unknown protobuf types raise explicit errors so integration issues surface quickly."""
        payload = encode_peripheral_payload(beats_streaming_pb2.Frame(png_data=b"x"))
        payload = payload.__class__(
            payload=payload.payload,
            encoding=payload.encoding,
            payload_type="heart.beats.streaming.Unknown",
        )

        with pytest.raises(PeripheralPayloadDecodeError):
            decode_peripheral_payload(payload)
