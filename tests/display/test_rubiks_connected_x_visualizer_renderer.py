"""Validate the Rubik's Connected X visualizer fills each panel edge to edge."""

from __future__ import annotations

import pygame

from heart import DeviceDisplayMode
from heart.device import Device
from heart.renderers.rubiks_connected_x_visualizer.renderer import (
    RubiksConnectedXVisualizerRenderer,
)
from heart.renderers.rubiks_connected_x_visualizer.state import (
    RubiksConnectedXVisualizerState,
)
from heart.runtime.display_context import DisplayContext


class TestRubiksConnectedXVisualizerRenderer:
    """Exercise the cube visualizer layout so the physical wraparound panels show full square faces without debug chrome."""

    def test_renderer_uses_full_display_mode(self) -> None:
        """Verify the visualizer renders against the full 4-panel atlas so each physical pane receives a single face instead of a mirrored strip copy."""

        renderer = RubiksConnectedXVisualizerRenderer()

        assert renderer.device_display_mode is DeviceDisplayMode.FULL

    def test_real_process_defaults_to_solved_faces_before_sync(
        self,
        device: Device,
    ) -> None:
        """Verify the pre-sync fallback still renders four distinct 3x3 faces so the wraparound panel geometry is readable before live packets arrive."""

        window = DisplayContext(
            device=device,
            screen=pygame.Surface(device.full_display_size()),
            clock=pygame.time.Clock(),
        )
        renderer = RubiksConnectedXVisualizerRenderer()
        renderer.set_state(RubiksConnectedXVisualizerState())
        renderer.initialized = True

        renderer.real_process(window, device.orientation)

        assert window.screen.get_at((8, 8))[:3] == (22, 163, 74)
        assert window.screen.get_at((74, 8))[:3] == (214, 45, 32)
        assert window.screen.get_at((138, 8))[:3] == (37, 99, 235)
        assert window.screen.get_at((202, 8))[:3] == (249, 115, 22)

    def test_real_process_fills_each_panel_edge_to_edge(
        self,
        device: Device,
    ) -> None:
        """Verify solved-face colors reach the outer panel edges so the wrapped cube display shows full faces without margins or labels."""

        window = DisplayContext(
            device=device,
            screen=pygame.Surface(device.full_display_size()),
            clock=pygame.time.Clock(),
        )
        renderer = RubiksConnectedXVisualizerRenderer()
        renderer.set_state(
            RubiksConnectedXVisualizerState(
                facelets="UUUUUUUUURRRRRRRRRFFFFFFFFFDDDDDDDDDLLLLLLLLLBBBBBBBBB",
                is_synced=True,
            )
        )
        renderer.initialized = True

        renderer.real_process(window, device.orientation)

        assert window.screen.get_at((8, 8))[:3] == (22, 163, 74)
        assert window.screen.get_at((53, 53))[:3] == (22, 163, 74)
        assert window.screen.get_at((74, 8))[:3] == (214, 45, 32)
        assert window.screen.get_at((117, 53))[:3] == (214, 45, 32)
        assert window.screen.get_at((138, 8))[:3] == (37, 99, 235)
        assert window.screen.get_at((181, 53))[:3] == (37, 99, 235)
        assert window.screen.get_at((202, 8))[:3] == (249, 115, 22)
        assert window.screen.get_at((245, 53))[:3] == (249, 115, 22)
