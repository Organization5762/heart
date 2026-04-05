"""BLE helpers and raw peripheral integration for Rubik's Connected X cubes."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable, Iterator, Sequence

import reactivex
from bleak import BleakClient, BleakScanner
from reactivex.subject import Subject

from heart.peripheral.core import Peripheral, PeripheralInfo, PeripheralTag
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

DEFAULT_SCAN_TIMEOUT_SECONDS = 8.0
DEFAULT_MONITOR_SECONDS = 30.0
DEFAULT_STATE_SYNC_TIMEOUT_SECONDS = 5.0
DEFAULT_RECONNECT_DELAY_SECONDS = 1.0
DEFAULT_IDLE_POLL_INTERVAL_SECONDS = 0.25
DEFAULT_STATE_REQUEST_INTERVAL_SECONDS = 0.15
DEFAULT_PERIODIC_STATE_REQUEST_SECONDS = 2.0
DEFAULT_RUNTIME_DEVICE_LOOKUP_TIMEOUT_SECONDS = 10.0
DEFAULT_BLUEZ_CONNECT_TIMEOUT_SECONDS = 8.0
DEFAULT_BLUEZ_CONNECT_RETRY_SECONDS = 5.0
MAX_FRAME_BUFFER_BYTES = 512
NORDIC_UART_SERVICE_UUID = "6e400001-b5a3-f393-e0a9-e50e24dcca9e"
NORDIC_UART_RX_CHARACTERISTIC_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"
RUBIKS_CONNECTED_X_ADDRESS_ENV_VAR = "HEART_RUBIKS_CONNECTED_X_ADDRESS"
RUBIKS_CONNECTED_X_AUTODETECT_ENV_VAR = "HEART_RUBIKS_CONNECTED_X_AUTODETECT"
RUBIKS_CONNECTED_X_PREFERRED_NAME_ENV_VAR = "HEART_RUBIKS_CONNECTED_X_PREFERRED_NAME"
RUBIKS_CONNECTED_X_IGNORE_STATE_SYNC_ENV_VAR = (
    "HEART_RUBIKS_CONNECTED_X_IGNORE_STATE_SYNC"
)
RUBIKS_CONNECTED_X_BASELINE_FACELETS_ENV_VAR = (
    "HEART_RUBIKS_CONNECTED_X_BASELINE_FACELETS"
)
RUBIKS_CONNECTED_X_BASELINE_PATH_ENV_VAR = "HEART_RUBIKS_CONNECTED_X_BASELINE_PATH"
DEFAULT_RUBIKS_CONNECTED_X_BASELINE_PATH = Path("rubiks_connected_x_baseline.txt")
RUBIKS_CONNECTED_X_BASELINE_CAPTURE_GESTURE = (
    "U",
    "U'",
    "U",
    "U'",
    "U",
    "U'",
    "U",
    "U'",
)
RUBIKS_CONNECTED_X_THREAD_NAME = "peripheral-rubiks-connected-x"
RUBIKS_CONNECTED_X_DISABLE_ORIENTATION_COMMAND = b"\x37"
RUBIKS_CONNECTED_X_REQUEST_STATE_COMMAND = b"\x33"
DEFAULT_RUBIKS_CONNECTED_X_ADDRESS = "E1:EE:92:6B:CF:CD"
DEFAULT_RUBIKS_CONNECTED_X_PREFERRED_NAME = "RubiksX_CDCF6B"
RUBIKS_CONNECTED_X_NAME_TOKENS = (
    "connected x",
    "connectedx",
    "rubik",
    "rubiksx",
)
RUBIKS_CONNECTED_X_AXIS_PERM = (5, 2, 0, 3, 1, 4)
RUBIKS_CONNECTED_X_FACE_ORDER = "URFDLB"
RUBIKS_CONNECTED_X_STATE_COLOR_ORDER = "BFUDRL"
RUBIKS_CONNECTED_X_STATE_FACE_PERM = (0, 1, 2, 5, 8, 7, 6, 3)
RUBIKS_CONNECTED_X_STATE_FACE_OFFSET = (0, 0, 6, 2, 0, 0)
RUBIKS_CONNECTED_X_SOLVED_FACELETS = (
    "UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB"
)
RUBIKS_CONNECTED_X_VISIBLE_FACE_ORDER = ("F", "R", "B", "L")


class RubiksConnectedXMessageType(StrEnum):
    """Known UART message types emitted by the cube."""

    MOVE = "move"
    STATE = "state"
    QUATERNION = "quaternion"
    BATTERY = "battery"
    OFFLINE_STATS = "offline_stats"
    CUBE_TYPE = "cube_type"


@dataclass(frozen=True, slots=True)
class RubiksConnectedXCandidate:
    """Summary of one BLE advertisement that may belong to the cube."""

    address: str
    name: str | None
    rssi: int | None
    service_uuids: tuple[str, ...] = ()
    manufacturer_ids: tuple[int, ...] = ()
    candidate_score: int = 0


@dataclass(frozen=True, slots=True)
class RubiksConnectedXCharacteristic:
    """Stable snapshot of a GATT characteristic."""

    uuid: str
    description: str
    properties: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RubiksConnectedXService:
    """Stable snapshot of a GATT service and its characteristics."""

    uuid: str
    description: str
    characteristics: tuple[RubiksConnectedXCharacteristic, ...]


@dataclass(frozen=True, slots=True)
class RubiksConnectedXNotification:
    """Raw BLE notification emitted by the cube."""

    characteristic_uuid: str
    payload_hex: str
    payload_utf8: str | None
    byte_count: int
    sequence: int
    parsed_packet: "RubiksConnectedXPacket | None" = None
    parsed_message: "RubiksConnectedXParsedMessage | None" = None


@dataclass(frozen=True, slots=True)
class RubiksConnectedXPacket:
    """Parsed UART frame emitted by the cube."""

    opcode: int
    face_index: int
    turn_code: int
    checksum_byte: int
    checksum_expected: int
    is_checksum_valid: bool
    raw_payload_hex: str


@dataclass(frozen=True, slots=True)
class RubiksConnectedXPacketSummary:
    """Count one parsed packet signature observed during calibration."""

    opcode: int
    face_index: int
    turn_code: int
    is_checksum_valid: bool
    count: int


@dataclass(frozen=True, slots=True)
class RubiksConnectedXMove:
    """One parsed face turn from a move message."""

    notation: str
    face: str
    raw_move_byte: int
    raw_timing_byte: int


@dataclass(frozen=True, slots=True)
class RubiksConnectedXParsedMessage:
    """Higher-level decode of one UART frame."""

    message_type: RubiksConnectedXMessageType
    moves: tuple[RubiksConnectedXMove, ...] = ()
    facelets: str | None = None
    battery_level: int | None = None


def normalize_candidate_name(name: str | None) -> str:
    """Normalize a BLE advertisement name for simple substring matching."""

    if name is None:
        return ""
    return " ".join(name.strip().lower().split())


def rubiks_connected_x_candidate_score(
    name: str | None,
    service_uuids: Sequence[str] = (),
) -> int:
    """Return a simple confidence score for likely cube advertisements."""

    normalized_name = normalize_candidate_name(name)
    score = 0
    if "connected x" in normalized_name or "connectedx" in normalized_name:
        score += 3
    if "rubiksx" in normalized_name:
        score += 3
    if "rubik" in normalized_name:
        score += 2
    if "connected" in normalized_name:
        score += 1
    lowered_service_uuids = {service_uuid.lower() for service_uuid in service_uuids}
    if NORDIC_UART_SERVICE_UUID in lowered_service_uuids:
        score += 3
    if any("aadb" in service_uuid for service_uuid in lowered_service_uuids):
        score += 1
    return score


def looks_like_rubiks_connected_x(
    name: str | None,
    service_uuids: Sequence[str] = (),
) -> bool:
    """Return whether an advertisement looks like the cube."""

    return rubiks_connected_x_candidate_score(name, service_uuids) > 0


def candidate_from_scan_result(
    device: Any,
    advertisement: Any | None,
) -> RubiksConnectedXCandidate:
    """Convert a bleak scan result into a stable candidate summary."""

    service_uuids = tuple(getattr(advertisement, "service_uuids", ()) or ())
    manufacturer_data = getattr(advertisement, "manufacturer_data", {}) or {}
    rssi = getattr(advertisement, "rssi", None)
    if rssi is None:
        rssi = getattr(device, "rssi", None)
    name = getattr(device, "name", None)
    return RubiksConnectedXCandidate(
        address=str(getattr(device, "address")),
        name=name,
        rssi=rssi,
        service_uuids=service_uuids,
        manufacturer_ids=tuple(sorted(int(key) for key in manufacturer_data.keys())),
        candidate_score=rubiks_connected_x_candidate_score(name, service_uuids),
    )


def snapshot_services(services: Iterable[Any]) -> tuple[RubiksConnectedXService, ...]:
    """Capture stable service metadata from a bleak service collection."""

    snapshots: list[RubiksConnectedXService] = []
    for service in services:
        characteristics = tuple(
            RubiksConnectedXCharacteristic(
                uuid=str(characteristic.uuid),
                description=str(getattr(characteristic, "description", "")),
                properties=tuple(
                    sorted(str(prop) for prop in characteristic.properties)
                ),
            )
            for characteristic in service.characteristics
        )
        snapshots.append(
            RubiksConnectedXService(
                uuid=str(service.uuid),
                description=str(getattr(service, "description", "")),
                characteristics=characteristics,
            )
        )
    return tuple(snapshots)


def render_candidate_line(candidate: RubiksConnectedXCandidate) -> str:
    """Render a short operator-facing description of one scan result."""

    name = candidate.name or "<unnamed>"
    return (
        f"score={candidate.candidate_score} address={candidate.address} "
        f"name={name!r} rssi={candidate.rssi} "
        f"services={list(candidate.service_uuids)} "
        f"manufacturer_ids={list(candidate.manufacturer_ids)}"
    )


def render_notification_line(notification: RubiksConnectedXNotification) -> str:
    """Render one raw notification for CLI logging and debugging."""

    utf8_fragment = notification.payload_utf8
    utf8_text = f" utf8={utf8_fragment!r}" if utf8_fragment is not None else ""
    parsed_text = ""
    if notification.parsed_message is not None:
        message = notification.parsed_message
        if message.message_type is RubiksConnectedXMessageType.MOVE:
            moves_text = ",".join(move.notation for move in message.moves) or "none"
            parsed_text = f" parsed(move={moves_text})"
        elif message.message_type is RubiksConnectedXMessageType.STATE:
            facelets_preview = (message.facelets or "")[:12]
            parsed_text = (
                " "
                f"parsed(state={facelets_preview}... len={len(message.facelets or '')})"
            )
        elif message.message_type is RubiksConnectedXMessageType.BATTERY:
            parsed_text = f" parsed(battery={message.battery_level})"
        else:
            parsed_text = f" parsed(type={message.message_type.value})"
    elif notification.parsed_packet is not None:
        packet = notification.parsed_packet
        parsed_text = (
            " "
            f"parsed(opcode={packet.opcode},"
            f" face={packet.face_index},"
            f" turn={packet.turn_code},"
            f" checksum={'ok' if packet.is_checksum_valid else 'bad'})"
        )
    return (
        f"packet={notification.sequence} char={notification.characteristic_uuid} "
        f"bytes={notification.byte_count} hex={notification.payload_hex}"
        f"{utf8_text}{parsed_text}"
    )


def serialize_rubiks_connected_x_notification(
    notification: RubiksConnectedXNotification,
) -> dict[str, Any]:
    """Convert one notification into a JSON-friendly dictionary."""

    parsed_packet = notification.parsed_packet
    parsed_payload = None
    if parsed_packet is not None:
        parsed_payload = {
            "opcode": parsed_packet.opcode,
            "face_index": parsed_packet.face_index,
            "turn_code": parsed_packet.turn_code,
            "checksum_byte": parsed_packet.checksum_byte,
            "checksum_expected": parsed_packet.checksum_expected,
            "is_checksum_valid": parsed_packet.is_checksum_valid,
            "raw_payload_hex": parsed_packet.raw_payload_hex,
        }
    parsed_message = notification.parsed_message
    parsed_message_payload = None
    if parsed_message is not None:
        parsed_message_payload = {
            "message_type": parsed_message.message_type.value,
            "moves": [
                {
                    "notation": move.notation,
                    "face": move.face,
                    "raw_move_byte": move.raw_move_byte,
                    "raw_timing_byte": move.raw_timing_byte,
                }
                for move in parsed_message.moves
            ],
            "facelets": parsed_message.facelets,
            "battery_level": parsed_message.battery_level,
        }
    return {
        "characteristic_uuid": notification.characteristic_uuid,
        "payload_hex": notification.payload_hex,
        "payload_utf8": notification.payload_utf8,
        "byte_count": notification.byte_count,
        "sequence": notification.sequence,
        "parsed_packet": parsed_payload,
        "parsed_message": parsed_message_payload,
    }


def _env_flag(name: str) -> bool:
    value = os.environ.get(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_valid_rubiks_connected_x_facelets(facelets: str | None) -> bool:
    """Return whether one facelet string can represent a full cube state."""

    if facelets is None:
        return False
    normalized = facelets.strip()
    if len(normalized) != len(RUBIKS_CONNECTED_X_SOLVED_FACELETS):
        return False
    return set(normalized) <= set(RUBIKS_CONNECTED_X_FACE_ORDER)


def rubiks_connected_x_baseline_path() -> Path:
    """Return the configured or default path for persisted local baselines."""

    configured = os.environ.get(RUBIKS_CONNECTED_X_BASELINE_PATH_ENV_VAR, "").strip()
    if configured:
        return Path(configured)
    return DEFAULT_RUBIKS_CONNECTED_X_BASELINE_PATH


def load_rubiks_connected_x_baseline_facelets() -> str | None:
    """Load one persisted local baseline facelet string if available."""

    configured_facelets = os.environ.get(RUBIKS_CONNECTED_X_BASELINE_FACELETS_ENV_VAR)
    if is_valid_rubiks_connected_x_facelets(configured_facelets):
        return configured_facelets.strip()
    path = rubiks_connected_x_baseline_path()
    if not path.exists():
        return None
    facelets = path.read_text(encoding="utf-8").strip()
    if not is_valid_rubiks_connected_x_facelets(facelets):
        logger.warning(
            "Rubik's Connected X baseline file %s does not contain 54 valid facelets.",
            path,
        )
        return None
    return facelets


def save_rubiks_connected_x_baseline_facelets(facelets: str) -> Path:
    """Persist one local baseline facelet string for future visualizer runs."""

    if not is_valid_rubiks_connected_x_facelets(facelets):
        raise ValueError("Rubik's Connected X baseline must contain 54 valid facelets.")
    path = rubiks_connected_x_baseline_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{facelets.strip()}\n", encoding="utf-8")
    return path


def _preferred_rubiks_connected_x_name() -> str:
    configured_name = os.environ.get(RUBIKS_CONNECTED_X_PREFERRED_NAME_ENV_VAR, "")
    normalized_name = configured_name.strip()
    if normalized_name:
        return normalized_name
    return DEFAULT_RUBIKS_CONNECTED_X_PREFERRED_NAME


def _candidate_priority(candidate: RubiksConnectedXCandidate) -> tuple[int, int, int, str]:
    preferred_name = _preferred_rubiks_connected_x_name()
    is_preferred_name = int((candidate.name or "") == preferred_name)
    return (
        is_preferred_name,
        candidate.candidate_score,
        candidate.rssi if candidate.rssi is not None else -999,
        candidate.name or "",
    )


def _decode_utf8_payload(payload: bytes) -> str | None:
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError:
        return None
    decoded = decoded.strip()
    return decoded or None


def _is_rubiks_connected_x_frame(payload: bytes) -> bool:
    return len(payload) >= 4 and payload[0] == 0x2A and payload[-2:] == b"\r\n"


def extract_rubiks_connected_x_frames(
    buffer: bytearray,
    chunk: bytes,
) -> tuple[bytes, ...]:
    """Reassemble UART frames from BLE notification chunks."""

    buffer.extend(chunk)
    frames: list[bytes] = []
    while True:
        start_index = buffer.find(b"\x2a")
        if start_index < 0:
            if len(buffer) > 1:
                del buffer[:-1]
            break
        if start_index > 0:
            del buffer[:start_index]

        end_index = buffer.find(b"\x0d\x0a", 2)
        if end_index < 0:
            if len(buffer) > MAX_FRAME_BUFFER_BYTES:
                del buffer[:-2]
            break

        frame_end = end_index + 2
        frames.append(bytes(buffer[:frame_end]))
        del buffer[:frame_end]
    return tuple(frames)


def parse_rubiks_connected_x_packet(payload: bytes) -> RubiksConnectedXPacket | None:
    """Parse one observed 8-byte cube packet.

    Observed frames currently follow the shape:
    `0x2A 0x06 opcode face turn checksum 0x0D 0x0A`
    where the checksum byte equals `0x30 + opcode + face + turn`.
    """

    if len(payload) != 8 or not _is_rubiks_connected_x_frame(payload):
        return None
    opcode = payload[2]
    face_index = payload[3]
    turn_code = payload[4]
    checksum_byte = payload[5]
    checksum_expected = 0x30 + opcode + face_index + turn_code
    return RubiksConnectedXPacket(
        opcode=opcode,
        face_index=face_index,
        turn_code=turn_code,
        checksum_byte=checksum_byte,
        checksum_expected=checksum_expected,
        is_checksum_valid=checksum_byte == checksum_expected,
        raw_payload_hex=payload.hex(" "),
    )


def parse_rubiks_connected_x_message(
    payload: bytes,
) -> RubiksConnectedXParsedMessage | None:
    """Parse one GoCube / Rubik's Connected UART frame."""

    if not _is_rubiks_connected_x_frame(payload):
        return None
    message_type = payload[2]
    if message_type == 1:
        return _parse_rubiks_connected_x_move_message(payload)
    if message_type == 2:
        facelets = parse_rubiks_connected_x_facelets(payload)
        if facelets is None:
            return None
        return RubiksConnectedXParsedMessage(
            message_type=RubiksConnectedXMessageType.STATE,
            facelets=facelets,
        )
    if message_type == 3:
        return RubiksConnectedXParsedMessage(
            message_type=RubiksConnectedXMessageType.QUATERNION
        )
    if message_type == 5 and len(payload) >= 7:
        return RubiksConnectedXParsedMessage(
            message_type=RubiksConnectedXMessageType.BATTERY,
            battery_level=payload[3],
        )
    if message_type == 7:
        return RubiksConnectedXParsedMessage(
            message_type=RubiksConnectedXMessageType.OFFLINE_STATS
        )
    if message_type == 8:
        return RubiksConnectedXParsedMessage(
            message_type=RubiksConnectedXMessageType.CUBE_TYPE
        )
    return None


def _parse_rubiks_connected_x_move_message(
    payload: bytes,
) -> RubiksConnectedXParsedMessage | None:
    message_length = len(payload) - 6
    if message_length < 2:
        return None
    moves: list[RubiksConnectedXMove] = []
    for offset in range(0, message_length, 2):
        move_index = 3 + offset
        timing_index = move_index + 1
        if timing_index >= len(payload) - 2:
            break
        raw_move_byte = payload[move_index]
        axis_index = raw_move_byte >> 1
        if axis_index >= len(RUBIKS_CONNECTED_X_AXIS_PERM):
            continue
        face = RUBIKS_CONNECTED_X_FACE_ORDER[RUBIKS_CONNECTED_X_AXIS_PERM[axis_index]]
        suffix = "'" if raw_move_byte & 0x01 else ""
        moves.append(
            RubiksConnectedXMove(
                notation=f"{face}{suffix}",
                face=face,
                raw_move_byte=raw_move_byte,
                raw_timing_byte=payload[timing_index],
            )
        )
    if not moves:
        return None
    return RubiksConnectedXParsedMessage(
        message_type=RubiksConnectedXMessageType.MOVE,
        moves=tuple(moves),
    )


def parse_rubiks_connected_x_facelets(payload: bytes) -> str | None:
    """Parse one full cube-state frame into standard URFDLB facelets."""

    if not _is_rubiks_connected_x_frame(payload) or payload[2] != 2:
        return None
    if len(payload) < 60:
        return None
    facelets: list[str] = ["?"] * len(RUBIKS_CONNECTED_X_SOLVED_FACELETS)
    for axis_index in range(6):
        facelet_offset = RUBIKS_CONNECTED_X_AXIS_PERM[axis_index] * 9
        face_offset = RUBIKS_CONNECTED_X_STATE_FACE_OFFSET[axis_index]
        center_color_value = payload[3 + axis_index * 9]
        if center_color_value >= len(RUBIKS_CONNECTED_X_STATE_COLOR_ORDER):
            return None
        facelets[facelet_offset + 4] = RUBIKS_CONNECTED_X_STATE_COLOR_ORDER[
            center_color_value
        ]
        for sticker_index in range(8):
            color_value = payload[3 + axis_index * 9 + sticker_index + 1]
            if color_value >= len(RUBIKS_CONNECTED_X_STATE_COLOR_ORDER):
                return None
            mapped_index = RUBIKS_CONNECTED_X_STATE_FACE_PERM[
                (sticker_index + face_offset) % 8
            ]
            facelets[facelet_offset + mapped_index] = (
                RUBIKS_CONNECTED_X_STATE_COLOR_ORDER[color_value]
            )
    return "".join(facelets)


def rubiks_connected_x_face_slice(facelets: str, face: str) -> str:
    """Return the 9 stickers for one face from a standard facelet string."""

    if len(facelets) != len(RUBIKS_CONNECTED_X_SOLVED_FACELETS):
        raise ValueError("Cube facelets must contain 54 stickers.")
    offset = RUBIKS_CONNECTED_X_FACE_ORDER.index(face) * 9
    return facelets[offset : offset + 9]


def summarize_rubiks_connected_x_notifications(
    notifications: Sequence[RubiksConnectedXNotification],
) -> tuple[RubiksConnectedXPacketSummary, ...]:
    """Count parsed packet signatures across a capture window."""

    counts = Counter(
        (
            packet.opcode,
            packet.face_index,
            packet.turn_code,
            packet.is_checksum_valid,
        )
        for notification in notifications
        if (packet := notification.parsed_packet) is not None
    )
    summaries = [
        RubiksConnectedXPacketSummary(
            opcode=opcode,
            face_index=face_index,
            turn_code=turn_code,
            is_checksum_valid=is_checksum_valid,
            count=count,
        )
        for (opcode, face_index, turn_code, is_checksum_valid), count in counts.items()
    ]
    return tuple(
        sorted(
            summaries,
            key=lambda summary: (
                -summary.count,
                summary.opcode,
                summary.face_index,
                summary.turn_code,
                summary.is_checksum_valid,
            ),
        )
    )


def _iter_scan_pairs(results: Any) -> Iterator[tuple[Any, Any | None]]:
    if isinstance(results, dict):
        for device, advertisement in results.values():
            yield device, advertisement
        return
    for device in results:
        yield device, None


async def discover_rubiks_connected_x_candidates(
    *,
    timeout_seconds: float = DEFAULT_SCAN_TIMEOUT_SECONDS,
    include_all: bool = False,
) -> list[RubiksConnectedXCandidate]:
    """Scan nearby BLE devices and return likely cube candidates."""

    scan_results = await _discover_rubiks_connected_x_scan_results(
        timeout_seconds=timeout_seconds,
        include_all=include_all,
    )
    return [candidate for _device, candidate in scan_results]


async def _discover_rubiks_connected_x_scan_results(
    *,
    timeout_seconds: float,
    include_all: bool,
) -> list[tuple[Any, RubiksConnectedXCandidate]]:
    """Return live BLE devices paired with their candidate summaries."""

    results = await BleakScanner.discover(timeout=timeout_seconds, return_adv=True)
    scan_results = [
        (device, candidate_from_scan_result(device, advertisement))
        for device, advertisement in _iter_scan_pairs(results)
    ]
    if not include_all:
        scan_results = [
            (device, candidate)
            for device, candidate in scan_results
            if looks_like_rubiks_connected_x(
                candidate.name,
                candidate.service_uuids,
            )
        ]
    return sorted(
        scan_results,
        key=lambda item: _candidate_priority(item[1]),
        reverse=True,
    )


async def inspect_rubiks_connected_x_services(
    address: str,
) -> tuple[RubiksConnectedXService, ...]:
    """Connect to a device and return a stable snapshot of its GATT map."""

    async with BleakClient(address) as client:
        services = client.services
        return snapshot_services(services)


async def resolve_rubiks_connected_x_candidate(
    *,
    address: str | None = None,
    timeout_seconds: float = DEFAULT_SCAN_TIMEOUT_SECONDS,
) -> RubiksConnectedXCandidate:
    """Resolve one target device either from an explicit address or from scanning."""

    if address is not None:
        candidates = await discover_rubiks_connected_x_candidates(
            timeout_seconds=timeout_seconds,
            include_all=True,
        )
        for candidate in candidates:
            if candidate.address == address:
                return candidate
        return RubiksConnectedXCandidate(
            address=address,
            name=None,
            rssi=None,
        )
    candidates = await discover_rubiks_connected_x_candidates(
        timeout_seconds=timeout_seconds,
        include_all=False,
    )
    if not candidates:
        raise ValueError("No Rubik's Connected X candidates were discovered.")
    return candidates[0]


def _select_notify_characteristics(
    services: Sequence[RubiksConnectedXService],
    *,
    characteristic_uuids: Sequence[str] | None = None,
) -> tuple[RubiksConnectedXCharacteristic, ...]:
    uuid_filter = {uuid.lower() for uuid in characteristic_uuids or ()}
    selected: list[RubiksConnectedXCharacteristic] = []
    for service in services:
        for characteristic in service.characteristics:
            properties = {prop.lower() for prop in characteristic.properties}
            is_notifiable = bool({"notify", "indicate"} & properties)
            if not is_notifiable:
                continue
            if uuid_filter and characteristic.uuid.lower() not in uuid_filter:
                continue
            selected.append(characteristic)
    return tuple(selected)


def _select_write_characteristic_uuid(
    services: Sequence[RubiksConnectedXService],
) -> str | None:
    fallback_uuid: str | None = None
    for service in services:
        for characteristic in service.characteristics:
            properties = {prop.lower() for prop in characteristic.properties}
            if not {"write", "write-without-response"} & properties:
                continue
            if characteristic.uuid.lower() == NORDIC_UART_RX_CHARACTERISTIC_UUID:
                return characteristic.uuid
            if fallback_uuid is None:
                fallback_uuid = characteristic.uuid
    return fallback_uuid


async def _send_rubiks_connected_x_command(
    client: BleakClient,
    characteristic_uuid: str,
    command: bytes,
    *,
    description: str,
) -> None:
    await client.write_gatt_char(
        characteristic_uuid,
        command,
        response=True,
    )
    logger.info(
        "Sent Rubik's Connected X command %s to %s",
        description,
        characteristic_uuid,
    )


async def _attempt_bluez_connect(address: str) -> bool:
    """Ask BlueZ to connect to the cube when bleak discovery alone is not enough."""

    if not sys.platform.startswith("linux"):
        return False

    def _run_connect() -> subprocess.CompletedProcess[str] | None:
        try:
            return subprocess.run(
                ["bluetoothctl", "connect", address],
                capture_output=True,
                text=True,
                timeout=DEFAULT_BLUEZ_CONNECT_TIMEOUT_SECONDS,
                check=False,
            )
        except FileNotFoundError:
            return None
        except subprocess.TimeoutExpired:
            logger.warning(
                "Timed out asking BlueZ to connect to Rubik's Connected X at %s",
                address,
            )
            return None

    result = await asyncio.to_thread(_run_connect)
    if result is None:
        return False
    combined_output = " ".join(
        part.strip() for part in (result.stdout, result.stderr) if part.strip()
    )
    if result.returncode == 0:
        logger.info(
            "Requested BlueZ connection to Rubik's Connected X at %s",
            address,
        )
        return True
    logger.debug(
        "BlueZ connect request for Rubik's Connected X at %s failed: %s",
        address,
        combined_output or f"returncode={result.returncode}",
    )
    return False


async def monitor_rubiks_connected_x_notifications(
    *,
    address: str | None = None,
    seconds: float = DEFAULT_MONITOR_SECONDS,
    characteristic_uuids: Sequence[str] | None = None,
    timeout_seconds: float = DEFAULT_SCAN_TIMEOUT_SECONDS,
    on_notification: Any | None = None,
) -> list[RubiksConnectedXNotification]:
    """Subscribe to notifiable characteristics and collect raw payloads."""

    candidate = await resolve_rubiks_connected_x_candidate(
        address=address,
        timeout_seconds=timeout_seconds,
    )
    notifications: list[RubiksConnectedXNotification] = []
    sequence = 0
    async with BleakClient(candidate.address) as client:
        services = snapshot_services(client.services)
        notify_characteristics = _select_notify_characteristics(
            services,
            characteristic_uuids=characteristic_uuids,
        )
        if not notify_characteristics:
            raise ValueError(
                "The target device has no notifiable or indicative characteristics."
            )
        frame_buffers: dict[str, bytearray] = {
            characteristic.uuid: bytearray()
            for characteristic in notify_characteristics
        }

        def build_callback(characteristic_uuid: str) -> Any:
            def _callback(_sender: Any, data: bytearray) -> None:
                nonlocal sequence
                for payload in extract_rubiks_connected_x_frames(
                    frame_buffers[characteristic_uuid],
                    bytes(data),
                ):
                    sequence += 1
                    parsed_message = parse_rubiks_connected_x_message(payload)
                    notification = RubiksConnectedXNotification(
                        characteristic_uuid=characteristic_uuid,
                        payload_hex=payload.hex(" "),
                        payload_utf8=_decode_utf8_payload(payload),
                        byte_count=len(payload),
                        sequence=sequence,
                        parsed_packet=parse_rubiks_connected_x_packet(payload),
                        parsed_message=parsed_message,
                    )
                    notifications.append(notification)
                    if on_notification is not None:
                        on_notification(notification)

            return _callback

        for characteristic in notify_characteristics:
            await client.start_notify(
                characteristic.uuid,
                build_callback(characteristic.uuid),
            )
        try:
            await asyncio.sleep(seconds)
        finally:
            for characteristic in notify_characteristics:
                try:
                    await client.stop_notify(characteristic.uuid)
                except Exception:
                    logger.debug(
                        "Stopping notification failed for %s",
                        characteristic.uuid,
                        exc_info=True,
                    )
    return notifications


async def request_rubiks_connected_x_state(
    *,
    address: str,
    characteristic_uuids: Sequence[str] | None = None,
    timeout_seconds: float = DEFAULT_STATE_SYNC_TIMEOUT_SECONDS,
) -> RubiksConnectedXNotification | None:
    """Request one full state frame and return the first decoded sync notification."""

    state_notification: RubiksConnectedXNotification | None = None
    sequence = 0
    loop = asyncio.get_running_loop()
    state_received = asyncio.Event()

    async with BleakClient(address) as client:
        services = snapshot_services(client.services)
        notify_characteristics = _select_notify_characteristics(
            services,
            characteristic_uuids=characteristic_uuids,
        )
        if not notify_characteristics:
            raise ValueError(
                "The target device has no notifiable or indicative characteristics."
            )
        write_characteristic_uuid = _select_write_characteristic_uuid(services)
        if write_characteristic_uuid is None:
            raise ValueError("The target device has no writable characteristic.")
        frame_buffers: dict[str, bytearray] = {
            characteristic.uuid: bytearray()
            for characteristic in notify_characteristics
        }

        def build_callback(characteristic_uuid: str) -> Any:
            def _callback(_sender: Any, data: bytearray) -> None:
                nonlocal sequence, state_notification
                for payload in extract_rubiks_connected_x_frames(
                    frame_buffers[characteristic_uuid],
                    bytes(data),
                ):
                    sequence += 1
                    parsed_message = parse_rubiks_connected_x_message(payload)
                    notification = RubiksConnectedXNotification(
                        characteristic_uuid=characteristic_uuid,
                        payload_hex=payload.hex(" "),
                        payload_utf8=_decode_utf8_payload(payload),
                        byte_count=len(payload),
                        sequence=sequence,
                        parsed_packet=parse_rubiks_connected_x_packet(payload),
                        parsed_message=parsed_message,
                    )
                    if (
                        parsed_message is not None
                        and parsed_message.message_type
                        is RubiksConnectedXMessageType.STATE
                        and state_notification is None
                    ):
                        state_notification = notification
                        loop.call_soon_threadsafe(state_received.set)

            return _callback

        for characteristic in notify_characteristics:
            await client.start_notify(
                characteristic.uuid,
                build_callback(characteristic.uuid),
            )
        try:
            await _send_rubiks_connected_x_command(
                client,
                write_characteristic_uuid,
                RUBIKS_CONNECTED_X_REQUEST_STATE_COMMAND,
                description="GetState",
            )
            try:
                await asyncio.wait_for(state_received.wait(), timeout=timeout_seconds)
            except TimeoutError:
                return None
        finally:
            for characteristic in notify_characteristics:
                try:
                    await client.stop_notify(characteristic.uuid)
                except Exception:
                    logger.debug(
                        "Stopping notification failed for %s",
                        characteristic.uuid,
                        exc_info=True,
                    )
    return state_notification


class RubiksConnectedXPeripheral(Peripheral[RubiksConnectedXNotification]):
    """Stream raw cube notifications into the Heart peripheral graph."""

    def __init__(
        self,
        *,
        address: str,
        name: str | None = None,
        characteristic_uuids: Sequence[str] | None = None,
    ) -> None:
        self.address = address
        self.name = name
        self.characteristic_uuids = tuple(characteristic_uuids or ())
        self._events: Subject[RubiksConnectedXNotification] = Subject()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._sequence = 0
        self._frame_buffers: dict[str, bytearray] = {}
        self._last_bluez_connect_attempt_monotonic = 0.0

    def _event_stream(self) -> reactivex.Observable[RubiksConnectedXNotification]:
        return self._events

    def peripheral_info(self) -> PeripheralInfo:
        return PeripheralInfo(
            id=f"rubiks-connected-x:{self.address}",
            tags=[
                PeripheralTag(name="input_variant", variant="ble_cube"),
                PeripheralTag(name="mode", variant="rubiks_connected_x"),
            ],
        )

    @classmethod
    def detect(cls) -> Iterator["RubiksConnectedXPeripheral"]:
        configured_address = os.environ.get(RUBIKS_CONNECTED_X_ADDRESS_ENV_VAR, "").strip()
        if configured_address:
            yield cls(
                address=configured_address,
                name=DEFAULT_RUBIKS_CONNECTED_X_PREFERRED_NAME,
            )
            return
        yield cls(
            address=DEFAULT_RUBIKS_CONNECTED_X_ADDRESS,
            name=DEFAULT_RUBIKS_CONNECTED_X_PREFERRED_NAME,
        )
        return

    def run(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            name=RUBIKS_CONNECTED_X_THREAD_NAME,
            target=self._run_thread,
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run_thread(self) -> None:
        try:
            asyncio.run(self._monitor_forever())
        except Exception:
            logger.exception("Rubik's Connected X monitor stopped unexpectedly.")

    async def _monitor_forever(self) -> None:
        while not self._stop_event.is_set():
            try:
                resolved_device = await self._resolve_runtime_device()
                resolved_address = str(getattr(resolved_device, "address", self.address))
                async with BleakClient(resolved_device) as client:
                    logger.info(
                        "Connected to Rubik's Connected X at %s",
                        resolved_address,
                    )
                    self._frame_buffers = {}
                    services = snapshot_services(client.services)
                    write_characteristic_uuid = _select_write_characteristic_uuid(
                        services
                    )
                    characteristics = _select_notify_characteristics(
                        services,
                        characteristic_uuids=self.characteristic_uuids,
                    )
                    if not characteristics:
                        logger.warning(
                            "Rubik's Connected X device %s has no notify characteristics.",
                            resolved_address,
                        )
                        return
                    pending_state_request = {"pending": False}
                    last_state_request_monotonic = 0.0
                    for characteristic in characteristics:
                        await client.start_notify(
                            characteristic.uuid,
                            self._build_notification_callback(
                                characteristic.uuid,
                                pending_state_request=pending_state_request,
                            ),
                        )
                    if write_characteristic_uuid is not None:
                        await _send_rubiks_connected_x_command(
                            client,
                            write_characteristic_uuid,
                            RUBIKS_CONNECTED_X_DISABLE_ORIENTATION_COMMAND,
                            description="DisableOrientation",
                        )
                        await _send_rubiks_connected_x_command(
                            client,
                            write_characteristic_uuid,
                            RUBIKS_CONNECTED_X_REQUEST_STATE_COMMAND,
                            description="GetState",
                        )
                        logger.info(
                            "Requested initial Rubik's Connected X state sync for %s",
                            resolved_address,
                        )
                        last_state_request_monotonic = time.monotonic()
                    while client.is_connected and not self._stop_event.is_set():
                        now = time.monotonic()
                        if (
                            pending_state_request["pending"]
                            and write_characteristic_uuid is not None
                        ):
                            if (
                                now - last_state_request_monotonic
                                >= DEFAULT_STATE_REQUEST_INTERVAL_SECONDS
                            ):
                                pending_state_request["pending"] = False
                                await _send_rubiks_connected_x_command(
                                    client,
                                    write_characteristic_uuid,
                                    RUBIKS_CONNECTED_X_REQUEST_STATE_COMMAND,
                                    description="GetState",
                                )
                                last_state_request_monotonic = now
                        elif (
                            write_characteristic_uuid is not None
                            and now - last_state_request_monotonic
                            >= DEFAULT_PERIODIC_STATE_REQUEST_SECONDS
                        ):
                            await _send_rubiks_connected_x_command(
                                client,
                                write_characteristic_uuid,
                                RUBIKS_CONNECTED_X_REQUEST_STATE_COMMAND,
                                description="GetState",
                            )
                            last_state_request_monotonic = now
                        await asyncio.sleep(DEFAULT_IDLE_POLL_INTERVAL_SECONDS)
            except Exception:
                if self._stop_event.is_set():
                    break
                logger.exception(
                    "Rubik's Connected X monitor failed for %s; retrying.",
                    self.address,
                )
            if not self._stop_event.is_set():
                await asyncio.sleep(DEFAULT_RECONNECT_DELAY_SECONDS)

    async def _resolve_runtime_device(self) -> Any:
        """Resolve a live BLE device object before connecting on Linux/BlueZ."""

        preferred_name = self.name or _preferred_rubiks_connected_x_name()
        if self.address is not None:
            device = await BleakScanner.find_device_by_address(
                self.address,
                timeout=DEFAULT_RUNTIME_DEVICE_LOOKUP_TIMEOUT_SECONDS,
            )
            if device is not None:
                return device
        if preferred_name:
            device = await BleakScanner.find_device_by_name(
                preferred_name,
                timeout=DEFAULT_RUNTIME_DEVICE_LOOKUP_TIMEOUT_SECONDS,
            )
            if device is not None:
                previous_address = self.address
                self.address = str(getattr(device, "address", self.address))
                self.name = str(getattr(device, "name", preferred_name))
                if previous_address and previous_address != self.address:
                    logger.info(
                        "Updated Rubik's Connected X address from %s to %s using preferred name %s",
                        previous_address,
                        self.address,
                        self.name,
                    )
                return device
        if self.address is not None:
            now = time.monotonic()
            if (
                now - self._last_bluez_connect_attempt_monotonic
                >= DEFAULT_BLUEZ_CONNECT_RETRY_SECONDS
            ):
                self._last_bluez_connect_attempt_monotonic = now
                if await _attempt_bluez_connect(self.address):
                    device = await BleakScanner.find_device_by_address(
                        self.address,
                        timeout=DEFAULT_RUNTIME_DEVICE_LOOKUP_TIMEOUT_SECONDS,
                    )
                    if device is not None:
                        return device
        candidates = await discover_rubiks_connected_x_candidates(include_all=False)
        if candidates:
            selected = candidates[0]
            previous_address = self.address
            self.address = selected.address
            self.name = selected.name
            logger.info(
                "Resolved Rubik's Connected X candidate for runtime: %s",
                render_candidate_line(selected),
            )
            if previous_address and previous_address != selected.address:
                logger.info(
                    "Updated Rubik's Connected X address from %s to %s using %s",
                    previous_address,
                    selected.address,
                    render_candidate_line(selected),
                )
            device = await BleakScanner.find_device_by_address(
                selected.address,
                timeout=DEFAULT_RUNTIME_DEVICE_LOOKUP_TIMEOUT_SECONDS,
            )
            if device is not None:
                return device
            now = time.monotonic()
            if (
                now - self._last_bluez_connect_attempt_monotonic
                >= DEFAULT_BLUEZ_CONNECT_RETRY_SECONDS
            ):
                self._last_bluez_connect_attempt_monotonic = now
                if await _attempt_bluez_connect(selected.address):
                    device = await BleakScanner.find_device_by_address(
                        selected.address,
                        timeout=DEFAULT_RUNTIME_DEVICE_LOOKUP_TIMEOUT_SECONDS,
                    )
                    if device is not None:
                        return device
        raise ValueError("No Rubik's Connected X candidates were discovered.")

    def _build_notification_callback(
        self,
        characteristic_uuid: str,
        *,
        pending_state_request: dict[str, bool] | None = None,
    ) -> Any:
        def _callback(_sender: Any, data: bytearray) -> None:
            frame_buffer = self._frame_buffers.setdefault(
                characteristic_uuid,
                bytearray(),
            )
            for payload in extract_rubiks_connected_x_frames(frame_buffer, bytes(data)):
                self._sequence += 1
                parsed_message = parse_rubiks_connected_x_message(payload)
                if (
                    pending_state_request is not None
                    and parsed_message is not None
                    and parsed_message.message_type is RubiksConnectedXMessageType.MOVE
                ):
                    pending_state_request["pending"] = True
                    logger.info(
                        "Observed Rubik's Connected X move(s): %s",
                        ",".join(move.notation for move in parsed_message.moves),
                    )
                elif (
                    parsed_message is not None
                    and parsed_message.message_type is RubiksConnectedXMessageType.STATE
                ):
                    logger.info("Observed Rubik's Connected X full state sync.")
                self._events.on_next(
                    RubiksConnectedXNotification(
                        characteristic_uuid=characteristic_uuid,
                        payload_hex=payload.hex(" "),
                        payload_utf8=_decode_utf8_payload(payload),
                        byte_count=len(payload),
                        sequence=self._sequence,
                        parsed_packet=parse_rubiks_connected_x_packet(payload),
                        parsed_message=parsed_message,
                    )
                )

        return _callback
