from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from manyfold import Subscribable
from manyfold.architecture import PubSubObservable

from heart.peripheral.core import PeripheralMessageEnvelope
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import StateProvider
from heart.peripheral.flowtoy import FlowToyPeripheral
from heart.peripheral.input_payloads import FlowToyPacket
from heart.renderers.flowtoy_spectrum.state import (FlowToySpectrumState,
                                                    FlowToySpectrumStop)

DEFAULT_FLOWTOY_RENDER_PERIOD_SECONDS = 3.0
DEFAULT_UNKNOWN_COLOR_SPECTRUM = (
    FlowToySpectrumStop(t=0.0, hex="#111111"),
    FlowToySpectrumStop(t=0.5, hex="#555555"),
    FlowToySpectrumStop(t=1.0, hex="#111111"),
)


class FlowToySpectrumStateProvider(StateProvider[FlowToySpectrumState]):
    def __init__(
        self, *, period_seconds: float = DEFAULT_FLOWTOY_RENDER_PERIOD_SECONDS
    ) -> None:
        self.period_seconds = period_seconds

    def initial_state(self) -> FlowToySpectrumState:
        return FlowToySpectrumState(color_spectrum=DEFAULT_UNKNOWN_COLOR_SPECTRUM)

    def states(
        self, peripheral_manager: PeripheralManager
    ) -> Subscribable[FlowToySpectrumState]:
        initial_state = self.initial_state()
        updates: list[object] = [
            peripheral_manager.input_io.frame_tick_stream().map(
                lambda frame_tick: (
                    lambda state: self._advance(state, frame_tick.delta_s)
                )
            )
        ]
        packet_stream = self._flowtoy_packet_stream(peripheral_manager)
        if packet_stream is not None:
            updates.append(
                packet_stream.map(
                    lambda packet: lambda state: self._apply_packet(state, packet)
                )
            )
        return PubSubObservable.merge(*updates).state(
            initial_state,
            lambda state, update: update(state),
        )

    def _flowtoy_packet_stream(
        self, peripheral_manager: PeripheralManager
    ) -> Subscribable[FlowToyPacket] | None:
        observables = [
            peripheral.observe
            for peripheral in peripheral_manager.peripherals
            if isinstance(peripheral, FlowToyPeripheral)
        ]
        if not observables:
            return None
        return PubSubObservable.merge(*observables).map(
            PeripheralMessageEnvelope[FlowToyPacket].unwrap_peripheral
        )

    def _advance(
        self, state: FlowToySpectrumState, delta_s: float
    ) -> FlowToySpectrumState:
        return replace(state, elapsed_s=max(0.0, state.elapsed_s + max(0.0, delta_s)))

    def _apply_packet(
        self, state: FlowToySpectrumState, packet: FlowToyPacket
    ) -> FlowToySpectrumState:
        decoded = packet.body.get("decoded")
        if not isinstance(decoded, Mapping):
            return state
        mode_documentation = decoded.get("mode_documentation")
        spectrum = self._color_spectrum(mode_documentation)
        display_name = "unknown"
        if isinstance(mode_documentation, Mapping):
            display_name_value = mode_documentation.get("display_name")
            if isinstance(display_name_value, str) and display_name_value:
                display_name = display_name_value
        return FlowToySpectrumState(
            group_id=self._int_value(decoded.get("group_id")),
            page=self._int_value(decoded.get("page")),
            mode=self._int_value(decoded.get("mode")),
            mode_name=self._string_value(
                decoded.get("mode_name"), fallback=state.mode_name
            ),
            display_name=display_name,
            elapsed_s=state.elapsed_s,
            color_spectrum=spectrum,
        )

    def _color_spectrum(
        self, mode_documentation: object
    ) -> tuple[FlowToySpectrumStop, ...]:
        if not isinstance(mode_documentation, Mapping):
            return DEFAULT_UNKNOWN_COLOR_SPECTRUM
        raw_spectrum = mode_documentation.get("color_spectrum")
        if not isinstance(raw_spectrum, list):
            return DEFAULT_UNKNOWN_COLOR_SPECTRUM
        spectrum: list[FlowToySpectrumStop] = []
        for stop in raw_spectrum:
            if not isinstance(stop, Mapping):
                continue
            stop_t = stop.get("t")
            stop_hex = stop.get("hex")
            if not isinstance(stop_t, (int, float)) or not isinstance(stop_hex, str):
                continue
            spectrum.append(FlowToySpectrumStop(t=float(stop_t), hex=stop_hex))
        if len(spectrum) < 2:
            return DEFAULT_UNKNOWN_COLOR_SPECTRUM
        return tuple(sorted(spectrum, key=lambda stop: stop.t))

    def _int_value(self, value: object) -> int:
        if isinstance(value, int):
            return value
        return 0

    def _string_value(self, value: object, *, fallback: str) -> str:
        if isinstance(value, str) and value:
            return value
        return fallback
