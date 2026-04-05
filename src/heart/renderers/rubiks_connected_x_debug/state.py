from __future__ import annotations

from dataclasses import dataclass

from heart.peripheral.rubiks_connected_x import RubiksConnectedXNotification


@dataclass(frozen=True)
class RubiksConnectedXDebugState:
    """Render-friendly snapshot of the cube debug stream."""

    status_lines: tuple[str, ...]
    packet_count: int = 0
    last_notification: RubiksConnectedXNotification | None = None
