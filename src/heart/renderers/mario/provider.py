
import time

import reactivex
from reactivex import operators as ops

from heart.assets.loader import Loader
from heart.display.models import KeyFrame
from heart.peripheral.providers.acceleration import AllAccelerometersProvider
from heart.peripheral.sensor import Acceleration
from heart.renderers.mario.state import MarioRendererState
from heart.utilities.logging import get_logger
from heart.utilities.reactivex_streams import share_stream

_LOGGER = get_logger(__name__)


class MarioRendererProvider:
    def __init__(
        self,
        metadata_file_path: str,
        sheet_file_path: str,
        accel_stream: AllAccelerometersProvider,
    ) -> None:
        self.metadata_file_path = metadata_file_path
        self.file = sheet_file_path
        self._accel_stream = accel_stream
        self._frames = self._load_frames(metadata_file_path)
        self._state_stream: reactivex.Observable[MarioRendererState] | None = None

    def _load_frames(self, metadata_file_path: str) -> list[KeyFrame]:
        frame_data = Loader.load_json(metadata_file_path)
        frames: list[KeyFrame] = []
        for key in frame_data["frames"]:
            frame_obj = frame_data["frames"][key]
            frame = frame_obj["frame"]
            frames.append(
                KeyFrame(
                    (frame["x"], frame["y"], frame["w"], frame["h"]),
                    frame_obj.get("duration"),
                )
            )
        if not frames:
            raise ValueError("Mario spritesheet metadata produced no frames")
        return frames

    def _create_initial_state(self) -> MarioRendererState:
        image = Loader.load_spirtesheet(self.file)
        return MarioRendererState(
            spritesheet=image,
            current_frame=self._frames[0],
            current_frame_index=0,
            time_since_last_update=None,
            in_loop=False,
            highest_z=0.0,
            latest_acceleration=None,
            last_update_time=None,
        )

    def _frame_duration(self, frame: KeyFrame) -> float:
        if frame.duration is None:
            return 100.0
        return max(float(frame.duration), 1.0)

    def _advance_frames(
        self,
        frame_index: int,
        time_since: float,
    ) -> tuple[int, float, bool]:
        duration = self._frame_duration(self._frames[frame_index])
        if time_since < duration:
            return frame_index, time_since, True
        next_index = frame_index + 1
        if next_index >= len(self._frames):
            return 0, 0.0, False
        return next_index, 0.0, True

    def _update_state(
        self,
        prev: MarioRendererState,
        acceleration: Acceleration,
    ) -> MarioRendererState:
        now = time.monotonic()
        last_time = prev.last_update_time or now
        delta_ms = max((now - last_time) * 1000.0, 0.0)

        frame_index = prev.current_frame_index
        time_since = prev.time_since_last_update
        in_loop = prev.in_loop
        highest_z = prev.highest_z

        if in_loop:
            time_since = (time_since or 0.0) + delta_ms
            frame_index, time_since, in_loop = self._advance_frames(
                frame_index, time_since
            )
        else:
            if acceleration.z > 11.0:
                highest_z = max(highest_z, acceleration.z)
                _LOGGER.info(
                    "Mario loop triggered by acceleration z=%.2f (max=%.2f)",
                    acceleration.z,
                    highest_z,
                )
                in_loop = True
                frame_index = 0
                time_since = 0.0

        if not in_loop:
            time_since = None
            frame_index = 0

        return MarioRendererState(
            spritesheet=prev.spritesheet,
            current_frame=self._frames[frame_index],
            current_frame_index=frame_index,
            time_since_last_update=time_since,
            in_loop=in_loop,
            highest_z=highest_z,
            latest_acceleration=acceleration,
            last_update_time=now,
        )

    def observable(self) -> reactivex.Observable[MarioRendererState]:
        if self._state_stream is None:
            initial = self._create_initial_state()
            source = self._accel_stream.observable()
            stream = source.pipe(
                ops.scan(self._update_state, seed=initial),
                ops.start_with(initial),
            )
            self._state_stream = share_stream(
                stream, stream_name="MarioRendererProvider.state"
            )
        return self._state_stream

    def state_updates(self) -> reactivex.Observable[MarioRendererState]:
        return self.observable()
