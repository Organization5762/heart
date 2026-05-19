"""Validate Mario renderer provider state transitions and observable wiring."""

from __future__ import annotations

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.sensor import Acceleration
from heart.renderers.mario.provider import MarioRendererProvider


class _SpriteSheetProbe:
    pass


class TestMarioRendererProvider:
    """Ensure MarioRendererProvider follows the shared renderer provider contract so container-backed renderers initialize cleanly."""

    def test_observable_accepts_peripheral_manager_and_emits_state(
        self,
        monkeypatch,
        stub_clock_factory,
    ) -> None:
        """Verify `observable(peripheral_manager)` works so StatefulBaseRenderer initialization does not fail at subscription time."""
        peripheral_manager = PeripheralManager()
        spritesheet = _SpriteSheetProbe()
        monkeypatch.setattr(
            peripheral_manager.input_io.debug_accelerometer,
            "should_use_debug_input",
            lambda: False,
        )
        monkeypatch.setattr(
            "heart.renderers.mario.provider.Loader.load_json",
            lambda _path: {
                "frames": {
                    "frame_0": {
                        "frame": {"x": 0, "y": 0, "w": 64, "h": 64},
                        "duration": 75,
                    }
                }
            },
        )
        monkeypatch.setattr(
            "heart.renderers.mario.provider.Loader.load_spirtesheet",
            lambda _path: spritesheet,
        )

        provider = MarioRendererProvider(
            metadata_file_path="mario_64.json",
            sheet_file_path="mario_64.png",
        )
        observed_states = []

        provider.observable(peripheral_manager).subscribe(observed_states.append)
        peripheral_manager.input_io.physical_acceleration().on_next(
            Acceleration(x=0.0, y=0.0, z=12.5)
        )
        peripheral_manager.input_io.frame_ticks.advance(
            stub_clock_factory(16, fps=60.0)
        )

        assert observed_states
        latest_state = observed_states[-1]
        assert latest_state.spritesheet is spritesheet
        assert latest_state.in_loop is True
        assert latest_state.highest_z == 12.5
        assert latest_state.latest_acceleration == Acceleration(x=0.0, y=0.0, z=12.5)

    def test_advance_state_advances_frames_while_in_loop(
        self,
        monkeypatch,
    ) -> None:
        """Confirm frame advancement uses elapsed clock time so Mario animation can progress once a jump loop has started."""
        spritesheet = _SpriteSheetProbe()
        monkeypatch.setattr(
            "heart.renderers.mario.provider.Loader.load_json",
            lambda _path: {
                "frames": {
                    "frame_0": {
                        "frame": {"x": 0, "y": 0, "w": 64, "h": 64},
                        "duration": 50,
                    },
                    "frame_1": {
                        "frame": {"x": 64, "y": 0, "w": 64, "h": 64},
                        "duration": 50,
                    },
                }
            },
        )
        monkeypatch.setattr(
            "heart.renderers.mario.provider.Loader.load_spirtesheet",
            lambda _path: spritesheet,
        )

        provider = MarioRendererProvider(
            metadata_file_path="mario_64.json",
            sheet_file_path="mario_64.png",
        )
        initial_state = provider._create_initial_state()
        started_state = provider._advance_state(
            state=initial_state,
            elapsed_ms=0.0,
            acceleration=Acceleration(x=0.0, y=0.0, z=12.0),
        )

        advanced_state = provider._advance_state(
            state=started_state,
            elapsed_ms=60.0,
            acceleration=None,
        )

        assert advanced_state.current_frame == 1
        assert advanced_state.in_loop is True
        assert advanced_state.time_since_last_update == 0.0
