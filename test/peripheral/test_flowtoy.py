from heart.peripheral.flowtoy import SyncPacket
import pytest

def test_change_mode() -> None:
    hex_lines = [
        "3dd55852000000030004010000000000000000040008"
        "3dd55853000000000004020000000000000000040108",
        "3cd55854000000000004030000000000000000040208"
    ]

    for i, packet in enumerate(hex_lines):
        parsed_packet = SyncPacket.parse_sync_packet(bytes.fromhex(packet))
        assert parsed_packet.mode == i

def test_change_page() -> None:
    hex_lines = [
        "37d55856000000000000000000000000000000000008"
        "38d55857000000000001000000000000000000010008",
        "3ad55858000000000002000000000000000000020008"
    ]

    for i, packet in enumerate(hex_lines):
        parsed_packet = SyncPacket.parse_sync_packet(bytes.fromhex(packet))
        assert parsed_packet.mode == i
