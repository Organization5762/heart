"""Verify the Rubik visualizer provider can recover from bad cube state syncs."""

from __future__ import annotations

from pathlib import Path

from heart.peripheral.rubiks_connected_x import (
    RUBIKS_CONNECTED_X_BASELINE_FACELETS_ENV_VAR,
    RUBIKS_CONNECTED_X_BASELINE_PATH_ENV_VAR,
    RUBIKS_CONNECTED_X_IGNORE_STATE_SYNC_ENV_VAR,
    RUBIKS_CONNECTED_X_SOLVED_FACELETS,
    load_rubiks_connected_x_baseline_facelets,
    RubiksConnectedXMessageType,
    RubiksConnectedXMove,
    RubiksConnectedXNotification,
    RubiksConnectedXParsedMessage,
)
from heart.renderers.rubiks_connected_x_visualizer.provider import (
    RubiksConnectedXVisualizerStateProvider,
)
from heart.renderers.rubiks_connected_x_visualizer.state import (
    RubiksConnectedXVisualizerState,
)
from heart.peripheral.rubiks_connected_x_state import apply_rubiks_connected_x_move


SCRAMBLED_BASELINE = apply_rubiks_connected_x_move(
    RUBIKS_CONNECTED_X_SOLVED_FACELETS,
    "U",
)


class TestRubiksConnectedXVisualizerStateProvider:
    """Exercise provider recovery paths so cube sync issues can be worked around without the phone app."""

    def test_state_sync_updates_visualizer_when_not_overridden(self) -> None:
        """Verify a full state sync replaces the fallback solved cube so normal BLE sync continues to reflect the cube's reported state."""

        provider = RubiksConnectedXVisualizerStateProvider()
        notification = RubiksConnectedXNotification(
            characteristic_uuid="test",
            payload_hex="",
            payload_utf8=None,
            byte_count=0,
            sequence=1,
            parsed_message=RubiksConnectedXParsedMessage(
                message_type=RubiksConnectedXMessageType.STATE,
                facelets="FRBLUBLUFDDUBRLFDBDFLFFRFBRRUURDLLLLBBRLDBFDRDUFBUUUR",
            ),
        )

        updated = provider._advance_state(RubiksConnectedXVisualizerState(), notification)

        assert (
            updated.facelets
            == "FRBLUBLUFDDUBRLFDBDFLFFRFBRRUURDLLLLBBRLDBFDRDUFBUUUR"
        )
        assert updated.is_synced is True

    def test_ignore_state_sync_keeps_local_solved_baseline_for_moves(
        self,
        monkeypatch,
    ) -> None:
        """Verify the local recovery flag ignores bad full-state packets so a physically solved cube can be re-baselined and tracked from moves only."""

        monkeypatch.setenv(RUBIKS_CONNECTED_X_IGNORE_STATE_SYNC_ENV_VAR, "1")
        provider = RubiksConnectedXVisualizerStateProvider()
        scrambled_state = RubiksConnectedXNotification(
            characteristic_uuid="test",
            payload_hex="",
            payload_utf8=None,
            byte_count=0,
            sequence=1,
            parsed_message=RubiksConnectedXParsedMessage(
                message_type=RubiksConnectedXMessageType.STATE,
                facelets="FRBLUBLUFDDUBRLFDBDFLFFRFBRRUURDLLLLBBRLDBFDRDUFBUUUR",
            ),
        )
        move = RubiksConnectedXNotification(
            characteristic_uuid="test",
            payload_hex="",
            payload_utf8=None,
            byte_count=0,
            sequence=2,
            parsed_message=RubiksConnectedXParsedMessage(
                message_type=RubiksConnectedXMessageType.MOVE,
                moves=(
                    RubiksConnectedXMove(
                        notation="U",
                        face="U",
                        raw_move_byte=0,
                        raw_timing_byte=0,
                    ),
                ),
            ),
        )

        ignored = provider._advance_state(RubiksConnectedXVisualizerState(), scrambled_state)
        moved = provider._advance_state(ignored, move)

        assert ignored.facelets == RUBIKS_CONNECTED_X_SOLVED_FACELETS
        assert ignored.is_synced is False
        assert moved.facelets != RUBIKS_CONNECTED_X_SOLVED_FACELETS
        assert moved.last_move == "U"

    def test_capture_gesture_saves_reported_state_as_new_baseline(
        self,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        """Verify the baked-in wiggle gesture persists the cube's currently reported state so operators can re-baseline a bad sync without leaving the visualizer."""

        baseline_path = tmp_path / "baseline.txt"
        monkeypatch.setenv(RUBIKS_CONNECTED_X_BASELINE_PATH_ENV_VAR, str(baseline_path))
        provider = RubiksConnectedXVisualizerStateProvider()
        state = RubiksConnectedXVisualizerState(
            facelets=RUBIKS_CONNECTED_X_SOLVED_FACELETS,
            recent_moves=("U", "U'", "U", "U'", "U", "U'", "U"),
            last_reported_facelets=SCRAMBLED_BASELINE,
        )

        updated = provider._advance_state(
            state,
            RubiksConnectedXNotification(
                characteristic_uuid="test",
                payload_hex="",
                payload_utf8=None,
                byte_count=0,
                sequence=9,
                parsed_message=RubiksConnectedXParsedMessage(
                    message_type=RubiksConnectedXMessageType.MOVE,
                    moves=(
                        RubiksConnectedXMove(
                            notation="U'",
                            face="U",
                            raw_move_byte=0,
                            raw_timing_byte=0,
                        ),
                    ),
                ),
            ),
        )

        assert updated.facelets == SCRAMBLED_BASELINE
        assert updated.last_move == "Baseline captured"
        assert load_rubiks_connected_x_baseline_facelets() == SCRAMBLED_BASELINE
        assert updated.facelets != RUBIKS_CONNECTED_X_SOLVED_FACELETS

    def test_baseline_facelets_mask_current_cube_state(
        self,
        monkeypatch,
    ) -> None:
        """Verify a configured baseline replaces the canonical solved cube so operators can treat the current scramble as solved and keep move tracking stable."""

        monkeypatch.setenv(
            RUBIKS_CONNECTED_X_BASELINE_FACELETS_ENV_VAR,
            SCRAMBLED_BASELINE,
        )
        provider = RubiksConnectedXVisualizerStateProvider()
        updated = provider._advance_state(
            RubiksConnectedXVisualizerState(
                facelets=SCRAMBLED_BASELINE,
            ),
            RubiksConnectedXNotification(
                characteristic_uuid="test",
                payload_hex="",
                payload_utf8=None,
                byte_count=0,
                sequence=2,
                parsed_message=RubiksConnectedXParsedMessage(
                    message_type=RubiksConnectedXMessageType.MOVE,
                    moves=(
                        RubiksConnectedXMove(
                            notation="U",
                            face="U",
                            raw_move_byte=0,
                            raw_timing_byte=0,
                        ),
                    ),
                ),
            ),
        )

        assert updated.facelets != SCRAMBLED_BASELINE
        assert updated.last_move == "U"

    def test_baseline_path_loads_facelets_from_disk(
        self,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        """Verify the provider can load a saved baseline file so the no-phone recovery flow survives terminal restarts and Pi service launches."""

        baseline_path = tmp_path / "baseline.txt"
        baseline_path.write_text(
            f"{SCRAMBLED_BASELINE}\n",
            encoding="utf-8",
        )
        monkeypatch.setenv(
            RUBIKS_CONNECTED_X_BASELINE_PATH_ENV_VAR,
            str(baseline_path),
        )
        provider = RubiksConnectedXVisualizerStateProvider()
        ignored = provider._advance_state(
            RubiksConnectedXVisualizerState(facelets=RUBIKS_CONNECTED_X_SOLVED_FACELETS),
            RubiksConnectedXNotification(
                characteristic_uuid="test",
                payload_hex="",
                payload_utf8=None,
                byte_count=0,
                sequence=1,
                parsed_message=RubiksConnectedXParsedMessage(
                    message_type=RubiksConnectedXMessageType.STATE,
                    facelets=RUBIKS_CONNECTED_X_SOLVED_FACELETS,
                ),
            ),
        )

        assert ignored.facelets == RUBIKS_CONNECTED_X_SOLVED_FACELETS
        assert ignored.is_synced is False
