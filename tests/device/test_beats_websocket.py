import json

from heart.device.beats.proto import beats_streaming_pb2
from heart.device.beats.websocket import _encode_peripheral_message
from heart.peripheral.core import PeripheralInfo, PeripheralMessageEnvelope


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
