from __future__ import annotations

import os

import reactivex
from reactivex import operators as ops

from heart.peripheral.core import PeripheralMessageEnvelope
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.rubiks_connected_x import (
    RUBIKS_CONNECTED_X_ADDRESS_ENV_VAR,
    RUBIKS_CONNECTED_X_IGNORE_STATE_SYNC_ENV_VAR,
    RUBIKS_CONNECTED_X_SOLVED_FACELETS,
    load_rubiks_connected_x_baseline_facelets,
    save_rubiks_connected_x_baseline_facelets,
    RubiksConnectedXMessageType,
    RubiksConnectedXNotification,
    RubiksConnectedXPeripheral,
)
from heart.peripheral.rubiks_connected_x_state import apply_rubiks_connected_x_moves
from heart.renderers.rubiks_connected_x_visualizer.state import (
    RubiksConnectedXVisualizerState,
)
from heart.utilities.logging import get_logger
from heart.utilities.reactivex_threads import (
    pipe_in_background,
    pipe_in_main_thread,
)

logger = get_logger(__name__)


def _ignore_state_sync() -> bool:
    value = os.environ.get(RUBIKS_CONNECTED_X_IGNORE_STATE_SYNC_ENV_VAR, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _use_local_baseline_mode() -> bool:
    return _ignore_state_sync() or load_rubiks_connected_x_baseline_facelets() is not None


class RubiksConnectedXVisualizerStateProvider(
    ObservableProvider[RubiksConnectedXVisualizerState]
):
    """Maintain the latest full cube state from Rubik's Connected X packets."""

    def observable(
        self,
        peripheral_manager: PeripheralManager,
    ) -> reactivex.Observable[RubiksConnectedXVisualizerState]:
        cube_peripherals = [
            peripheral
            for peripheral in peripheral_manager.peripherals
            if isinstance(peripheral, RubiksConnectedXPeripheral)
        ]
        if not cube_peripherals:
            return reactivex.just(RubiksConnectedXVisualizerState())

        initial_state = RubiksConnectedXVisualizerState(
            facelets=load_rubiks_connected_x_baseline_facelets()
            or RUBIKS_CONNECTED_X_SOLVED_FACELETS,
            last_move=(
                "Set "
                f"{RUBIKS_CONNECTED_X_ADDRESS_ENV_VAR} "
                "to the cube address if auto-detect is disabled."
            ),
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
        return pipe_in_main_thread(
            merged,
            ops.scan(self._advance_state, seed=initial_state),
            ops.start_with(initial_state),
            ops.share(),
        )

    def _advance_state(
        self,
        state: RubiksConnectedXVisualizerState,
        notification: RubiksConnectedXNotification,
    ) -> RubiksConnectedXVisualizerState:
        parsed_message = notification.parsed_message
        facelets = state.facelets
        last_move = state.last_move
        is_synced = state.is_synced
        recent_moves = state.recent_moves
        last_reported_facelets = state.last_reported_facelets
        if parsed_message is not None:
            if (
                parsed_message.message_type is RubiksConnectedXMessageType.STATE
                and parsed_message.facelets is not None
            ):
                last_reported_facelets = parsed_message.facelets
                if _use_local_baseline_mode():
                    logger.info(
                        "Ignoring Rubik's Connected X state sync because local baseline mode is enabled."
                    )
                else:
                    facelets = parsed_message.facelets
                    is_synced = True
                    logger.info(
                        "Visualizer applied Rubik's Connected X state sync. facelets=%s...",
                        facelets[:12],
                    )
            elif (
                parsed_message.message_type is RubiksConnectedXMessageType.MOVE
                and parsed_message.moves
            ):
                last_move = parsed_message.moves[-1].notation
                recent_moves = (
                    recent_moves
                    + tuple(move.notation for move in parsed_message.moves)
                )[-len(state.baseline_capture_gesture) :]
                seed_facelets = (
                    facelets
                    or load_rubiks_connected_x_baseline_facelets()
                    or RUBIKS_CONNECTED_X_SOLVED_FACELETS
                )
                facelets = apply_rubiks_connected_x_moves(
                    seed_facelets,
                    tuple(move.notation for move in parsed_message.moves),
                )
                if recent_moves == state.baseline_capture_gesture:
                    baseline_facelets = last_reported_facelets or facelets
                    path = save_rubiks_connected_x_baseline_facelets(
                        baseline_facelets
                    )
                    facelets = baseline_facelets
                    is_synced = False
                    last_move = "Baseline captured"
                    logger.info(
                        "Captured Rubik's Connected X local baseline via gesture and saved it to %s",
                        path,
                    )
                logger.info(
                    "Visualizer applied Rubik's Connected X move(s): %s",
                    ",".join(move.notation for move in parsed_message.moves),
                )
        return RubiksConnectedXVisualizerState(
            facelets=facelets,
            is_synced=is_synced,
            packet_count=state.packet_count + 1,
            last_move=last_move,
            last_notification=notification,
            visible_faces=state.visible_faces,
            recent_moves=recent_moves,
            last_reported_facelets=last_reported_facelets,
            baseline_capture_gesture=state.baseline_capture_gesture,
        )
