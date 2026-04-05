from __future__ import annotations

import reactivex
from reactivex import operators as ops

from heart.peripheral.core import PeripheralMessageEnvelope
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.rubiks_connected_x import (
    RUBIKS_CONNECTED_X_ADDRESS_ENV_VAR,
    RubiksConnectedXMessageType,
    RubiksConnectedXNotification,
    RubiksConnectedXPeripheral,
)
from heart.renderers.rubiks_connected_x_debug.state import RubiksConnectedXDebugState
from heart.utilities.reactivex_threads import pipe_in_background

DEFAULT_STATUS_LINES = (
    "Rubik's Connected X debug mode",
    "Set HEART_RUBIKS_CONNECTED_X_ADDRESS to the cube BLE address.",
    "Run `totem rubiks-connected-x scan --all` to discover candidates.",
)


class RubiksConnectedXDebugStateProvider(
    ObservableProvider[RubiksConnectedXDebugState]
):
    """Expose the latest raw cube notification as simple text lines."""

    def observable(
        self,
        peripheral_manager: PeripheralManager,
    ) -> reactivex.Observable[RubiksConnectedXDebugState]:
        cube_peripherals = [
            peripheral
            for peripheral in peripheral_manager.peripherals
            if isinstance(peripheral, RubiksConnectedXPeripheral)
        ]
        if not cube_peripherals:
            return reactivex.just(
                RubiksConnectedXDebugState(status_lines=DEFAULT_STATUS_LINES)
            )

        first_peripheral = cube_peripherals[0]
        initial_state = RubiksConnectedXDebugState(
            status_lines=(
                "Rubik's Connected X debug mode",
                f"Configured address: {first_peripheral.address}",
                "Twist the cube to capture raw BLE notifications.",
                f"Env var: {RUBIKS_CONNECTED_X_ADDRESS_ENV_VAR}",
            )
        )
        observables = [peripheral.observe for peripheral in cube_peripherals]
        merged = pipe_in_background(
            reactivex.merge(*observables),
            ops.map(
                PeripheralMessageEnvelope[
                    RubiksConnectedXNotification
                ].unwrap_peripheral
            ),
        )
        return pipe_in_background(
            merged,
            ops.scan(self._advance_state, seed=initial_state),
            ops.start_with(initial_state),
            ops.share(),
        )

    def _advance_state(
        self,
        state: RubiksConnectedXDebugState,
        notification: RubiksConnectedXNotification,
    ) -> RubiksConnectedXDebugState:
        utf8_fragment = notification.payload_utf8 or "<binary>"
        parsed_packet = notification.parsed_packet
        parsed_line = "Parsed: <unrecognized>"
        parsed_message = notification.parsed_message
        if parsed_message is not None:
            if parsed_message.message_type is RubiksConnectedXMessageType.MOVE:
                parsed_line = (
                    "Parsed: "
                    f"move={','.join(move.notation for move in parsed_message.moves)}"
                )
            elif parsed_message.message_type is RubiksConnectedXMessageType.STATE:
                parsed_line = "Parsed: full cube state sync"
            elif parsed_message.message_type is RubiksConnectedXMessageType.BATTERY:
                parsed_line = f"Parsed: battery={parsed_message.battery_level}"
            else:
                parsed_line = f"Parsed: type={parsed_message.message_type.value}"
        elif parsed_packet is not None:
            parsed_line = (
                "Parsed: "
                f"opcode={parsed_packet.opcode} "
                f"face={parsed_packet.face_index} "
                f"turn={parsed_packet.turn_code} "
                f"checksum={'ok' if parsed_packet.is_checksum_valid else 'bad'}"
            )
        status_lines = (
            "Rubik's Connected X debug mode",
            f"Packets observed: {state.packet_count + 1}",
            f"Characteristic: {notification.characteristic_uuid}",
            f"Bytes: {notification.byte_count}",
            parsed_line,
            f"UTF-8: {utf8_fragment}",
            f"HEX: {notification.payload_hex}",
        )
        return RubiksConnectedXDebugState(
            status_lines=status_lines,
            packet_count=state.packet_count + 1,
            last_notification=notification,
        )
