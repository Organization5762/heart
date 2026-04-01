"""Validate device selection so Beats forwarding preserves the totem atlas geometry."""

from __future__ import annotations

from heart.device import Rectangle
from heart.device.selection import _select_streamed_device


class TestStreamedDeviceSelection:
    """Ensure Beats device selection preserves the expected 4x1 cube strip so websocket frames map cleanly onto the totem."""

    def test_streamed_device_forces_cube_orientation(self, monkeypatch) -> None:
        """Verify Beats forwarding ignores non-cube layout requests so the streamed atlas remains 256x64 for the totem surfaces."""
        monkeypatch.setattr(
            "heart.device.selection.Configuration.forward_to_beats_app",
            lambda: True,
        )

        device = _select_streamed_device(Rectangle.with_layout(1, 1))

        assert device is not None
        assert device.orientation.layout.columns == 4
        assert device.orientation.layout.rows == 1
        assert device.full_display_size() == (256, 64)
