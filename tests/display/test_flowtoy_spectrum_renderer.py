from __future__ import annotations

from collections.abc import Iterator

import pygame

from heart.device import Rectangle
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.flowtoy import FlowToyPeripheral
from heart.peripheral.input_payloads import FlowToyPacket
from heart.peripheral.radio import RadioDriver, RawRadioPacket
from heart.renderers.flowtoy_spectrum import (FlowToySpectrumRenderer,
                                              FlowToySpectrumState,
                                              FlowToySpectrumStateProvider,
                                              FlowToySpectrumStop)


class DummyRadioDriver(RadioDriver):
    """Provide deterministic FlowToy packets so renderer tests can drive the provider directly."""

    def __init__(self, *, port: str = "/dev/ttyACM9") -> None:
        self.port = port

    def packets(self) -> Iterator[RawRadioPacket]:
        yield from ()

    def send_raw_command(self, command: str) -> None:
        return None

    def close(self) -> None:
        return None


class TestFlowToySpectrumStateProvider:
    """Validate FlowToy spectrum state updates so renderer inputs stay synchronized with live radio packets."""

    def test_provider_tracks_latest_packet_and_elapsed_time(
        self,
        stub_clock_factory,
    ) -> None:
        """Verify the provider captures FlowToy mode metadata and advances elapsed time so the renderer can animate a live spectrum reliably."""
        manager = PeripheralManager()
        provider = FlowToySpectrumStateProvider()
        peripheral = FlowToyPeripheral(driver=DummyRadioDriver())
        manager.register(peripheral)
        observed: list[FlowToySpectrumState] = []

        subscription = provider.observable(manager).subscribe(on_next=observed.append)
        try:
            peripheral.process_packet(
                RawRadioPacket(
                    payload=bytes(
                        [
                            0x00,
                            0x01,
                            0x02,
                            0x00,
                            0x00,
                            0x00,
                            0x01,
                            0x02,
                            0x03,
                            0x04,
                            10,
                            20,
                            30,
                            40,
                            50,
                            0b0000_0011,
                            0x00,
                            0x00,
                            2,
                            7,
                            0b0000_0010,
                        ]
                    ),
                    protocol="flowtoy",
                )
            )

            clock = stub_clock_factory(250)
            manager.frame_tick_controller.advance(clock)
        finally:
            subscription.dispose()

        assert observed[0].mode_name == "flowtoy-unknown"
        latest = observed[-1]
        assert latest.group_id == 1
        assert latest.page == 2
        assert latest.mode == 7
        assert latest.mode_name == "flowtoy-page-2-mode-7"
        assert latest.display_name == "unicorn"
        assert latest.elapsed_s == 0.25
        assert latest.color_spectrum == (
            FlowToySpectrumStop(t=0.0, hex="#ffd6f6"),
            FlowToySpectrumStop(t=0.25, hex="#d9c2ff"),
            FlowToySpectrumStop(t=0.5, hex="#9be7ff"),
            FlowToySpectrumStop(t=0.75, hex="#b8ffd6"),
            FlowToySpectrumStop(t=1.0, hex="#fffdf7"),
        )


class TestFlowToySpectrumRenderer:
    """Exercise FlowToy spectrum drawing so palette reconstruction remains visually aligned with decoded radio state."""

    def test_renderer_draws_expected_colors_from_spectrum(self) -> None:
        """Verify the renderer maps circular spectrum time to on-screen color positions so a decoded mode produces a faithful visual preview."""
        renderer = FlowToySpectrumRenderer()
        renderer.set_state(
            FlowToySpectrumState(
                group_id=0,
                page=1,
                mode=1,
                mode_name="flowtoy-page-1-mode-1",
                display_name="rainbow",
                elapsed_s=0.0,
                color_spectrum=(
                    FlowToySpectrumStop(t=0.0, hex="#ff0000"),
                    FlowToySpectrumStop(t=0.5, hex="#00ff00"),
                    FlowToySpectrumStop(t=1.0, hex="#ff0000"),
                ),
            )
        )
        renderer.initialized = True

        manager = PeripheralManager()
        orientation = Rectangle.with_layout(1, 1)
        window = pygame.Surface((65, 65))

        renderer._internal_process(window, manager, orientation)

        right_color = window.get_at((56, 32))
        left_color = window.get_at((8, 32))

        assert right_color.r > 200
        assert right_color.g < 80
        assert left_color.g > 200
        assert left_color.r < 80

    def test_renderer_uses_group_id_to_offset_phase(self) -> None:
        """Verify group identifiers produce stable phase offsets so different FlowToy groups do not render as indistinguishable clones."""
        renderer = FlowToySpectrumRenderer()
        renderer.set_state(
            FlowToySpectrumState(
                group_id=90,
                page=1,
                mode=1,
                mode_name="flowtoy-page-1-mode-1",
                display_name="rainbow",
                elapsed_s=0.0,
                color_spectrum=(
                    FlowToySpectrumStop(t=0.0, hex="#ff0000"),
                    FlowToySpectrumStop(t=0.25, hex="#0000ff"),
                    FlowToySpectrumStop(t=0.5, hex="#00ff00"),
                    FlowToySpectrumStop(t=1.0, hex="#ff0000"),
                ),
            )
        )
        renderer.initialized = True

        manager = PeripheralManager()
        orientation = Rectangle.with_layout(1, 1)
        window = pygame.Surface((65, 65))

        renderer._internal_process(window, manager, orientation)

        right_color = window.get_at((56, 32))

        assert right_color.b > 180
        assert right_color.r < 120


class TestFlowToyPacketPayloadShape:
    """Keep FlowToy packet helpers explicit in renderer tests so state sources remain understandable."""

    def test_packet_to_input_keeps_mode_name(self) -> None:
        """Verify FlowToy packet payload helpers preserve mode names so renderer-facing debugging stays legible when packets are inspected manually."""
        packet = FlowToyPacket(body={"decoded": {"page": 1, "mode": 1}}, mode_name="flowtoy-page-1-mode-1")

        rendered = packet.to_input()

        assert rendered.data["mode_name"] == "flowtoy-page-1-mode-1"
