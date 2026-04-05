from __future__ import annotations

from dataclasses import dataclass

from heart.peripheral.rubiks_connected_x import (
    RUBIKS_CONNECTED_X_BASELINE_CAPTURE_GESTURE,
    RUBIKS_CONNECTED_X_SOLVED_FACELETS,
    RUBIKS_CONNECTED_X_VISIBLE_FACE_ORDER,
    RubiksConnectedXNotification,
)


@dataclass(frozen=True)
class RubiksConnectedXVisualizerState:
    """Render-friendly snapshot of the latest cube state."""

    facelets: str | None = RUBIKS_CONNECTED_X_SOLVED_FACELETS
    is_synced: bool = False
    packet_count: int = 0
    last_move: str | None = None
    last_notification: RubiksConnectedXNotification | None = None
    visible_faces: tuple[str, ...] = RUBIKS_CONNECTED_X_VISIBLE_FACE_ORDER
    recent_moves: tuple[str, ...] = ()
    last_reported_facelets: str | None = None
    baseline_capture_gesture: tuple[str, ...] = (
        RUBIKS_CONNECTED_X_BASELINE_CAPTURE_GESTURE
    )
