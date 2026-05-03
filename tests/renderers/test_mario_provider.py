"""Validate Mario renderer provider state transitions and observable wiring."""

from __future__ import annotations

import reactivex
from reactivex.subject import BehaviorSubject, Subject

from heart.peripheral.core.input import FrameTick
from heart.peripheral.sensor import Acceleration
from heart.renderers.mario.provider import MarioRendererProvider


class _StubSpritesheet:
    pass


class _StubAccelerationController:
    def __init__(self) -> None:
        self._stream: BehaviorSubject[Acceleration | None] = BehaviorSubject(None)

    def observable(self) -> reactivex.Observable[Acceleration | None]:
        return self._stream

    def emit(self, acceleration: Acceleration | None) -> None:
        self._stream.on_next(acceleration)


class _StubAccelerationDebugProfile(_StubAccelerationController):
    def __init__(self, should_use_debug_input: bool) -> None:
        super().__init__()
        self._should_use_debug_input = should_use_debug_input

    def should_use_debug_input(self) -> bool:
        return self._should_use_debug_input


class _StubFrameTickController:
    def __init__(self) -> None:
        self._stream: Subject[FrameTick] = Subject()

    def observable(self) -> reactivex.Observable[FrameTick]:
        return self._stream

    def emit(self, frame_tick: FrameTick) -> None:
        self._stream.on_next(frame_tick)


class _StubPeripheralManager:
    def __init__(self) -> None:
        self.frame_tick_controller = _StubFrameTickController()


class TestMarioRendererProvider:
    """Ensure MarioRendererProvider follows the shared renderer provider contract so container-backed renderers initialize cleanly."""

    def test_observable_accepts_peripheral_manager_and_emits_state(
        self,
        monkeypatch,
    ) -> None:
        """Verify `observable(peripheral_manager)` works so StatefulBaseRenderer initialization does not fail at subscription time."""
        accelerometer_controller = _StubAccelerationController()
        accelerometer_debug_profile = _StubAccelerationDebugProfile(
            should_use_debug_input=False
        )
        spritesheet = _StubSpritesheet()
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
            accelerometer_controller=accelerometer_controller,
            accelerometer_debug_profile=accelerometer_debug_profile,
        )
        peripheral_manager = _StubPeripheralManager()
        observed_states = []

        provider.observable(peripheral_manager).subscribe(observed_states.append)
        accelerometer_controller.emit(Acceleration(x=0.0, y=0.0, z=12.5))
        peripheral_manager.frame_tick_controller.emit(
            FrameTick(
                frame_index=0,
                delta_ms=16.0,
                delta_s=0.016,
                monotonic_s=1.0,
                fps=60.0,
            )
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
        accelerometer_controller = _StubAccelerationController()
        accelerometer_debug_profile = _StubAccelerationDebugProfile(
            should_use_debug_input=False
        )
        spritesheet = _StubSpritesheet()
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
            accelerometer_controller=accelerometer_controller,
            accelerometer_debug_profile=accelerometer_debug_profile,
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
