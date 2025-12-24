import time

import reactivex

from heart.assets.loader import Loader
from heart.display.models import KeyFrame
from heart.modules.devices.acceleration.provider import AllAccelerometersProvider
from heart.modules.mario.state import MarioRendererState
from heart.peripheral.sensor import Acceleration
from heart.peripheral.uwb import ops


class MarioRendererProvider:
    #     self._spritesheet: pygame.Surface | None = None

    def __init__(
        self,
        metadata_file_path: str,
        sheet_file_path: str,
        accel_stream: AllAccelerometersProvider,
    ) -> None:
        self.metadata_file_path = metadata_file_path
        self.file = sheet_file_path
        self._accel_stream = accel_stream

        frame_data = Loader.load_json(self.metadata_file_path)
        self.frames = []
        for key in frame_data["frames"]:
            frame_obj = frame_data["frames"][key]
            frame = frame_obj["frame"]
            self.frames.append(
                KeyFrame(
                    (frame["x"], frame["y"], frame["w"], frame["h"]),
                    frame_obj["duration"],
                )
            )

    def _create_initial_state(
        self,
    ) -> MarioRendererState:
        image = Loader.load_spirtesheet(self.file)
        return MarioRendererState(spritesheet=image)


    def observable(
        self,
    ) -> reactivex.Observable[MarioRendererState]:
        observable = self._accel_stream.observable()

        initial = self._create_initial_state()
        last_update_time: float | None = None

        def update_state(prev: MarioRendererState, acceleration: Acceleration):
            nonlocal last_update_time
            now = time.monotonic()
            if last_update_time is None:
                delta_ms = 0.0
            else:
                delta_ms = (now - last_update_time) * 1000.0
            last_update_time = now

            current_kf = self.frames[prev.current_frame]
            current_frame = prev.current_frame
            time_since_last_update = prev.time_since_last_update
            in_loop = prev.in_loop
            highest_z = prev.highest_z

            kf_duration = current_kf.duration

            if in_loop:
                if time_since_last_update is None:
                    time_since_last_update = 0.0

                time_since_last_update += delta_ms

                if time_since_last_update > kf_duration:
                    current_frame += 1
                    time_since_last_update = 0

                    if current_frame >= len(self.frames):
                        current_frame = 0
                        in_loop = False
            else:
                vector = prev.latest_acceleration
                if vector is not None and vector.z > 11.0:  # vibes based constants
                    highest_z = max(highest_z, vector.z)
                    print(f"highest z: {highest_z}, accel z: {vector.z}")
                    in_loop = True
                    time_since_last_update = 0

            if not in_loop:
                time_since_last_update = None

            return MarioRendererState(
                spritesheet=prev.spritesheet,
                current_frame=current_frame,
                time_since_last_update=time_since_last_update,
                in_loop=in_loop,
                highest_z=highest_z,
                latest_acceleration=acceleration,
            )

        return observable.pipe(
            ops.start_with(initial),
            ops.scan(update_state),
            ops.share(),
        )
