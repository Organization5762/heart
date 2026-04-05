"""Validate Rubik's Connected X BLE helpers without requiring hardware."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import heart.peripheral.rubiks_connected_x as rubiks_connected_x_module
from heart.peripheral.rubiks_connected_x import (
    DEFAULT_RUBIKS_CONNECTED_X_ADDRESS,
    DEFAULT_RUBIKS_CONNECTED_X_PREFERRED_NAME,
    RUBIKS_CONNECTED_X_ADDRESS_ENV_VAR,
    RUBIKS_CONNECTED_X_SOLVED_FACELETS,
    RubiksConnectedXMessageType,
    RubiksConnectedXNotification,
    RubiksConnectedXPeripheral,
    candidate_from_scan_result,
    extract_rubiks_connected_x_frames,
    normalize_candidate_name,
    parse_rubiks_connected_x_facelets,
    parse_rubiks_connected_x_message,
    parse_rubiks_connected_x_packet,
    render_candidate_line,
    render_notification_line,
    rubiks_connected_x_candidate_score,
    rubiks_connected_x_face_slice,
    serialize_rubiks_connected_x_notification,
    snapshot_services,
    summarize_rubiks_connected_x_notifications,
)


class TestRubiksConnectedXHelpers:
    """Cover scan helper behaviour so cube discovery stays predictable before hardware decoding lands."""

    @staticmethod
    def _solved_state_payload() -> bytes:
        """Return one solved-state frame for parser and framing tests."""

        return bytes(
            [
                0x2A,
                0x06,
                0x02,
                *([0] * 9),
                *([1] * 9),
                *([2] * 9),
                *([3] * 9),
                *([4] * 9),
                *([5] * 9),
                0x00,
                0x0D,
                0x0A,
            ]
        )

    def test_normalize_candidate_name_handles_missing_values(self) -> None:
        """Verify name normalization tolerates absent BLE names so scans stay robust around anonymous advertisements."""

        assert normalize_candidate_name(None) == ""
        assert (
            normalize_candidate_name("  Rubik's   Connected X  ")
            == "rubik's connected x"
        )

    def test_candidate_score_prefers_connected_x_names(self) -> None:
        """Verify candidate scoring prioritizes Connected X naming so likely cubes rise to the top during scans."""

        assert rubiks_connected_x_candidate_score("Rubik's Connected X") > 0
        assert rubiks_connected_x_candidate_score("ConnectedX Cube") > 0
        assert (
            rubiks_connected_x_candidate_score(
                "RubiksX_CDCF6B",
                ["6e400001-b5a3-f393-e0a9-e50e24dcca9e"],
        )
            >= 6
        )
        assert rubiks_connected_x_candidate_score("Noise Cancelling Headphones") == 0

    def test_candidate_score_prefers_the_known_cube_name(self) -> None:
        """Verify the configured RubiksX device name sorts first so Pi autodetect locks onto the intended cube when multiple smart cubes are nearby."""

        preferred_candidate = candidate_from_scan_result(
            SimpleNamespace(address="AA", name="RubiksX_CDCF6B"),
            SimpleNamespace(
                rssi=-70,
                service_uuids=["6e400001-b5a3-f393-e0a9-e50e24dcca9e"],
                manufacturer_data={},
            ),
        )
        generic_candidate = candidate_from_scan_result(
            SimpleNamespace(address="BB", name="Rubik's Connected X"),
            SimpleNamespace(
                rssi=-30,
                service_uuids=["6e400001-b5a3-f393-e0a9-e50e24dcca9e"],
                manufacturer_data={},
            ),
        )

        ordered = sorted(
            [generic_candidate, preferred_candidate],
            key=lambda candidate: (
                int((candidate.name or "") == "RubiksX_CDCF6B"),
                candidate.candidate_score,
                candidate.rssi if candidate.rssi is not None else -999,
                candidate.name or "",
            ),
            reverse=True,
        )

        assert ordered[0].name == "RubiksX_CDCF6B"

    def test_candidate_from_scan_result_preserves_metadata(self) -> None:
        """Verify scan summaries keep service and manufacturer metadata so live debugging can correlate advertisements with devices."""

        device = SimpleNamespace(address="AA:BB:CC:DD", name="Rubik's Connected X")
        advertisement = SimpleNamespace(
            rssi=-55,
            service_uuids=["1234", "5678"],
            manufacturer_data={1: b"\x01", 76: b"\x02"},
        )

        candidate = candidate_from_scan_result(device, advertisement)

        assert candidate.address == "AA:BB:CC:DD"
        assert candidate.name == "Rubik's Connected X"
        assert candidate.rssi == -55
        assert candidate.service_uuids == ("1234", "5678")
        assert candidate.manufacturer_ids == (1, 76)
        assert "AA:BB:CC:DD" in render_candidate_line(candidate)

    def test_snapshot_services_captures_characteristics(self) -> None:
        """Verify service snapshots preserve characteristic UUIDs and properties so GATT inspection output remains stable across bleak objects."""

        services = [
            SimpleNamespace(
                uuid="service-1",
                description="Test Service",
                characteristics=[
                    SimpleNamespace(
                        uuid="char-1",
                        description="Notify One",
                        properties=["notify", "read"],
                    )
                ],
            )
        ]

        snapshots = snapshot_services(services)

        assert len(snapshots) == 1
        assert snapshots[0].uuid == "service-1"
        assert snapshots[0].characteristics[0].uuid == "char-1"
        assert snapshots[0].characteristics[0].properties == ("notify", "read")

    def test_parse_packet_validates_observed_checksum_pattern(self) -> None:
        """Verify the parser decodes observed cube packets so new modes can consume structured fields instead of raw hex."""

        packet = parse_rubiks_connected_x_packet(
            bytes.fromhex("2a 06 01 01 09 3b 0d 0a")
        )

        assert packet is not None
        assert packet.opcode == 1
        assert packet.face_index == 1
        assert packet.turn_code == 9
        assert packet.checksum_expected == 0x3B
        assert packet.is_checksum_valid is True

    def test_parse_packet_marks_bad_checksum(self) -> None:
        """Verify checksum mismatches are surfaced so live debugging can distinguish malformed frames from valid turns."""

        packet = parse_rubiks_connected_x_packet(
            bytes.fromhex("2a 06 01 01 09 30 0d 0a")
        )

        assert packet is not None
        assert packet.is_checksum_valid is False

    def test_parse_message_decodes_move_notation(self) -> None:
        """Verify move messages decode into face turns so renderers can react to semantic cube moves instead of raw bytes."""

        parsed_message = parse_rubiks_connected_x_message(
            bytes.fromhex("2a 06 01 04 00 35 0d 0a")
        )

        assert parsed_message is not None
        assert parsed_message.message_type is RubiksConnectedXMessageType.MOVE
        assert parsed_message.moves[0].notation == "U"

    def test_parse_message_decodes_inverse_move_notation(self) -> None:
        """Verify inverse move messages preserve turn direction so live state sync can distinguish clockwise from counterclockwise turns."""

        parsed_message = parse_rubiks_connected_x_message(
            bytes.fromhex("2a 06 01 05 09 3f 0d 0a")
        )

        assert parsed_message is not None
        assert parsed_message.message_type is RubiksConnectedXMessageType.MOVE
        assert parsed_message.moves[0].notation == "U'"

    def test_parse_facelets_decodes_solved_cube_state(self) -> None:
        """Verify full state frames decode into standard facelets so the visualizer can render the live cube without calibration heuristics."""

        solved_state_payload = self._solved_state_payload()

        facelets = parse_rubiks_connected_x_facelets(solved_state_payload)

        assert facelets == RUBIKS_CONNECTED_X_SOLVED_FACELETS
        assert rubiks_connected_x_face_slice(facelets, "F") == "FFFFFFFFF"

    def test_parse_facelets_accepts_non_move_header_byte(self) -> None:
        """Verify frame parsing does not assume the move-packet header byte so larger state responses can still decode into live cube facelets."""

        payload = bytearray(self._solved_state_payload())
        payload[1] = 0x38

        facelets = parse_rubiks_connected_x_facelets(bytes(payload))

        assert facelets == RUBIKS_CONNECTED_X_SOLVED_FACELETS

    def test_extract_frames_reassembles_split_state_payload(self) -> None:
        """Verify split BLE notifications are reassembled into one full UART frame so full-state sync survives Nordic UART chunking."""

        payload = self._solved_state_payload()
        buffer = bytearray()

        first = extract_rubiks_connected_x_frames(buffer, payload[:19])
        second = extract_rubiks_connected_x_frames(buffer, payload[19:41])
        third = extract_rubiks_connected_x_frames(buffer, payload[41:])

        assert first == ()
        assert second == ()
        assert third == (payload,)
        assert buffer == bytearray()
        assert (
            parse_rubiks_connected_x_message(third[0]).message_type
            is RubiksConnectedXMessageType.STATE
        )

    def test_extract_frames_returns_multiple_packets_from_one_chunk(self) -> None:
        """Verify chunk parsing can emit multiple frames so back-to-back move packets are not dropped when BLE coalesces notifications."""

        move_payload = bytes.fromhex("2a 06 01 04 00 35 0d 0a")
        buffer = bytearray()

        frames = extract_rubiks_connected_x_frames(
            buffer,
            move_payload + move_payload,
        )

        assert frames == (move_payload, move_payload)
        assert buffer == bytearray()

    def test_extract_frames_recovers_non_move_header_frame(self) -> None:
        """Verify frame extraction keys off the actual UART start byte so full-state packets are not discarded for using a different header byte than moves."""

        payload = bytearray(self._solved_state_payload())
        payload[1] = 0x38
        buffer = bytearray()

        frames = extract_rubiks_connected_x_frames(buffer, bytes(payload))

        assert frames == (bytes(payload),)
        assert buffer == bytearray()

    def test_render_notification_line_includes_parsed_summary(self) -> None:
        """Verify the monitor output includes parsed field summaries so reverse-engineering sessions stay readable on the command line."""

        packet = parse_rubiks_connected_x_packet(
            bytes.fromhex("2a 06 01 02 00 33 0d 0a")
        )
        parsed_message = parse_rubiks_connected_x_message(
            bytes.fromhex("2a 06 01 02 00 33 0d 0a")
        )
        notification = RubiksConnectedXNotification(
            characteristic_uuid="6e400003-b5a3-f393-e0a9-e50e24dcca9e",
            payload_hex="2a 06 01 02 00 33 0d 0a",
            payload_utf8="*\x06\x01\x02\x003",
            byte_count=8,
            sequence=12,
            parsed_packet=packet,
            parsed_message=parsed_message,
        )

        rendered = render_notification_line(notification)

        assert "parsed(move=F)" in rendered

    def test_serialize_notification_includes_parsed_packet_payload(self) -> None:
        """Verify notification serialization keeps parsed packet fields so saved calibration reports remain useful after the live session ends."""

        packet = parse_rubiks_connected_x_packet(
            bytes.fromhex("2a 06 01 02 00 33 0d 0a")
        )
        parsed_message = parse_rubiks_connected_x_message(
            bytes.fromhex("2a 06 01 02 00 33 0d 0a")
        )
        notification = RubiksConnectedXNotification(
            characteristic_uuid="6e400003-b5a3-f393-e0a9-e50e24dcca9e",
            payload_hex="2a 06 01 02 00 33 0d 0a",
            payload_utf8="*\x06\x01\x02\x003",
            byte_count=8,
            sequence=12,
            parsed_packet=packet,
            parsed_message=parsed_message,
        )

        serialized = serialize_rubiks_connected_x_notification(notification)

        assert serialized["sequence"] == 12
        assert serialized["parsed_packet"] is not None
        assert serialized["parsed_packet"]["face_index"] == 2
        assert serialized["parsed_message"] is not None
        assert serialized["parsed_message"]["moves"][0]["notation"] == "F"

    def test_summarize_notifications_counts_matching_packets(self) -> None:
        """Verify packet summaries group repeated signatures so calibration output highlights the stable face-turn combinations for each labeled move."""

        packet = parse_rubiks_connected_x_packet(
            bytes.fromhex("2a 06 01 02 00 33 0d 0a")
        )
        notifications = [
            RubiksConnectedXNotification(
                characteristic_uuid="6e400003-b5a3-f393-e0a9-e50e24dcca9e",
                payload_hex="2a 06 01 02 00 33 0d 0a",
                payload_utf8="*\x06\x01\x02\x003",
                byte_count=8,
                sequence=12,
                parsed_packet=packet,
            ),
            RubiksConnectedXNotification(
                characteristic_uuid="6e400003-b5a3-f393-e0a9-e50e24dcca9e",
                payload_hex="2a 06 01 02 00 33 0d 0a",
                payload_utf8="*\x06\x01\x02\x003",
                byte_count=8,
                sequence=13,
                parsed_packet=packet,
            ),
        ]

        summaries = summarize_rubiks_connected_x_notifications(notifications)

        assert len(summaries) == 1
        assert summaries[0].face_index == 2
        assert summaries[0].turn_code == 0
        assert summaries[0].count == 2

    def test_detect_uses_configured_address(self, monkeypatch) -> None:
        """Verify peripheral detection honors the configured address so laptop workflows can bind to one chosen cube deterministically."""

        monkeypatch.setenv(RUBIKS_CONNECTED_X_ADDRESS_ENV_VAR, "AA:BB:CC:DD")

        peripherals = list(RubiksConnectedXPeripheral.detect())

        assert len(peripherals) == 1
        assert peripherals[0].address == "AA:BB:CC:DD"
        assert peripherals[0].name == DEFAULT_RUBIKS_CONNECTED_X_PREFERRED_NAME

    def test_detect_defaults_to_the_known_cube_address(self, monkeypatch) -> None:
        """Verify peripheral detection defaults to the team's single Rubik cube so the visualizer works without extra address setup in the common workflow."""

        monkeypatch.delenv(RUBIKS_CONNECTED_X_ADDRESS_ENV_VAR, raising=False)

        peripherals = list(RubiksConnectedXPeripheral.detect())

        assert len(peripherals) == 1
        assert peripherals[0].address == DEFAULT_RUBIKS_CONNECTED_X_ADDRESS
        assert peripherals[0].name == DEFAULT_RUBIKS_CONNECTED_X_PREFERRED_NAME

    def test_resolve_runtime_device_attempts_bluez_connect_for_known_address(
        self,
        monkeypatch,
    ) -> None:
        """Verify runtime resolution asks BlueZ to connect a configured cube so Pi service restarts can recover without manual shell intervention."""

        peripheral = RubiksConnectedXPeripheral(address="AA:BB:CC:DD")
        resolved_device = SimpleNamespace(address="AA:BB:CC:DD", name="RubiksX_CDCF6B")
        calls = {"find_by_address": 0, "bluez_connect": 0}

        async def fake_find_device_by_address(address: str, timeout: float):
            calls["find_by_address"] += 1
            assert address == "AA:BB:CC:DD"
            if calls["find_by_address"] == 1:
                return None
            return resolved_device

        async def fake_find_device_by_name(name: str, timeout: float):
            assert name == "RubiksX_CDCF6B"
            return None

        async def fake_attempt_bluez_connect(address: str) -> bool:
            calls["bluez_connect"] += 1
            assert address == "AA:BB:CC:DD"
            return True

        async def fake_discover_candidates(*, include_all: bool):
            raise AssertionError("BlueZ fallback should resolve before scanning candidates.")

        monkeypatch.setattr(
            rubiks_connected_x_module.BleakScanner,
            "find_device_by_address",
            fake_find_device_by_address,
        )
        monkeypatch.setattr(
            rubiks_connected_x_module.BleakScanner,
            "find_device_by_name",
            fake_find_device_by_name,
        )
        monkeypatch.setattr(
            rubiks_connected_x_module,
            "_attempt_bluez_connect",
            fake_attempt_bluez_connect,
        )
        monkeypatch.setattr(
            rubiks_connected_x_module,
            "discover_rubiks_connected_x_candidates",
            fake_discover_candidates,
        )

        device = asyncio.run(peripheral._resolve_runtime_device())

        assert device is resolved_device
        assert calls["bluez_connect"] == 1
