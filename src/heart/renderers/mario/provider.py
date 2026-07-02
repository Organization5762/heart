from heart.assets.loader import Loader
from heart.display.models import KeyFrame
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.peripheral.core.variables import Variable
from heart.peripheral.sensor import Acceleration
from heart.renderers.mario.state import MarioRendererState
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class MarioRendererProvider(ObservableProvider[MarioRendererState]):
    def __init__(
        self,
        metadata_file_path: str,
        sheet_file_path: str,
    ):
        self.metadata_file_path = metadata_file_path
        self.file = sheet_file_path
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

    def _create_initial_state(self) -> MarioRendererState:
        image = Loader.load_spirtesheet(self.file)
        return MarioRendererState(spritesheet=image)

    def _advance_state(
        self,
        state: MarioRendererState,
        *,
        elapsed_ms: float,
        acceleration: Acceleration | None,
    ) -> MarioRendererState:
        current_frame = state.current_frame
        time_since_last_update = state.time_since_last_update
        in_loop = state.in_loop
        highest_z = state.highest_z
        current_keyframe = self.frames[current_frame]
        keyframe_duration = current_keyframe.duration or 0
        if in_loop:
            next_time = (time_since_last_update or 0.0) + elapsed_ms
            if next_time > keyframe_duration:
                current_frame += 1
                next_time = 0.0
                if current_frame >= len(self.frames):
                    current_frame = 0
                    in_loop = False
                    next_time = 0.0
            time_since_last_update = next_time if in_loop else None
        elif acceleration is not None and acceleration.z > 11.0:
            highest_z = max(highest_z, acceleration.z)
            logger.info(
                "Highest accel Z updated: highest_z=%s, accel_z=%s",
                highest_z,
                acceleration.z,
            )
            in_loop = True
            time_since_last_update = 0.0
        else:
            time_since_last_update = None
        return MarioRendererState(
            spritesheet=state.spritesheet,
            current_frame=current_frame,
            time_since_last_update=time_since_last_update,
            in_loop=in_loop,
            highest_z=highest_z,
            latest_acceleration=acceleration,
        )

    def observable(
        self, peripheral_manager: PeripheralManager
    ) -> Variable[MarioRendererState]:
        initial = self._create_initial_state()
        accelerations = peripheral_manager.input_io.active_acceleration().start_with(
            None
        )
        frame_ticks = peripheral_manager.input_io.frame_tick_stream()
        return (
            frame_ticks.with_latest_from(accelerations)
            .scan(
                lambda state, latest: self._advance_state(
                    state=state,
                    elapsed_ms=float(latest[0].delta_ms),
                    acceleration=latest[1],
                ),
                seed=initial,
            )
            .start_with(initial)
        )
