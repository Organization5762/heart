
from __future__ import annotations

from dataclasses import replace

import reactivex
from reactivex import operators as ops

from heart.assets.loader import Loader
from heart.display.models import KeyFrame
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.providers.acceleration import AllAccelerometersProvider
from heart.peripheral.sensor import Acceleration
from heart.renderers.mario.state import MarioRendererState
from heart.utilities.logging import get_logger
from heart.utilities.reactivex_streams import share_stream

logger = get_logger(__name__)


class MarioRendererProvider:
    def __init__(
        self,
        metadata_file_path: str,
        sheet_file_path: str,
        accel_stream: AllAccelerometersProvider,
        peripheral_manager: PeripheralManager,
        *,
        trigger_threshold: float = 11.0,
    ) -> None:
        self.metadata_file_path = metadata_file_path
        self.file = sheet_file_path
        self._accel_stream = accel_stream
        self._peripheral_manager = peripheral_manager
        self._trigger_threshold = trigger_threshold
        self._state_stream: reactivex.Observable[MarioRendererState] | None = None

        frame_data = Loader.load_json(self.metadata_file_path)
        self.frames: list[KeyFrame] = []
        for key in frame_data["frames"]:
            frame_obj = frame_data["frames"][key]
            frame = frame_obj["frame"]
            self.frames.append(
                KeyFrame(
                    (frame["x"], frame["y"], frame["w"], frame["h"]),
                    frame_obj["duration"],
                )
            )
        if not self.frames:
            raise ValueError("Mario renderer frames could not be loaded")

    def _create_initial_state(self) -> MarioRendererState:
        image = Loader.load_spirtesheet(self.file)
        initial_frame = self.frames[0]
        return MarioRendererState(
            spritesheet=image,
            current_frame_index=0,
            current_frame=initial_frame,
        )

    def _handle_acceleration(
        self, state: MarioRendererState, acceleration: Acceleration
    ) -> MarioRendererState:
        highest_z = max(state.highest_z, acceleration.z)
        updates = {
            "latest_acceleration": acceleration,
            "highest_z": highest_z,
        }
        if not state.in_loop and acceleration.z > self._trigger_threshold:
            logger.debug(
                "Mario jump triggered (highest_z=%.2f, accel_z=%.2f)",
                highest_z,
                acceleration.z,
            )
            updates.update(
                {
                    "in_loop": True,
                    "time_since_last_update": 0.0,
                    "current_frame_index": 0,
                    "current_frame": self.frames[0],
                }
            )
        return replace(state, **updates)

    def _advance_animation(
        self, state: MarioRendererState, *, elapsed_ms: float
    ) -> MarioRendererState:
        if not state.in_loop:
            if state.time_since_last_update is None:
                return state
            return replace(state, time_since_last_update=None)

        previous_elapsed = state.time_since_last_update or 0.0
        time_since_last_update = previous_elapsed + elapsed_ms
        current_frame = state.current_frame or self.frames[state.current_frame_index]
        duration = current_frame.duration or 0

        if duration <= 0 or time_since_last_update >= duration:
            next_index = state.current_frame_index + 1
            if next_index >= len(self.frames):
                return replace(
                    state,
                    current_frame_index=0,
                    current_frame=self.frames[0],
                    in_loop=False,
                    time_since_last_update=None,
                )
            return replace(
                state,
                current_frame_index=next_index,
                current_frame=self.frames[next_index],
                time_since_last_update=0.0,
            )

        return replace(state, time_since_last_update=time_since_last_update)

    def _build_state_stream(self) -> reactivex.Observable[MarioRendererState]:
        initial = self._create_initial_state()
        accelerations = self._accel_stream.observable()
        tick_stream = self._peripheral_manager.game_tick
        clocks = self._peripheral_manager.clock.pipe(
            ops.filter(lambda clock: clock is not None),
            ops.share(),
        )

        accel_updates = accelerations.pipe(
            ops.map(lambda accel: lambda state: self._handle_acceleration(state, accel))
        )

        tick_updates = tick_stream.pipe(
            ops.with_latest_from(clocks),
            ops.map(
                lambda latest: lambda state: self._advance_animation(
                    state,
                    elapsed_ms=latest[1].get_time(),
                )
            ),
        )

        state_stream = reactivex.merge(accel_updates, tick_updates).pipe(
            ops.scan(lambda state, update: update(state), seed=initial),
            ops.start_with(initial),
        )
        return share_stream(state_stream, stream_name="MarioRendererProvider.state")

    def observable(self) -> reactivex.Observable[MarioRendererState]:
        if self._state_stream is None:
            self._state_stream = self._build_state_stream()
        return self._state_stream
