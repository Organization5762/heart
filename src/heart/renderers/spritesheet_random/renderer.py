import reactivex

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.spritesheet_random.provider import \
    SpritesheetLoopRandomProvider
from heart.renderers.spritesheet_random.state import SpritesheetLoopRandomState
from heart.runtime.display_context import DisplayContext


class SpritesheetLoopRandom(StatefulBaseRenderer[SpritesheetLoopRandomState]):
    def __init__(
        self,
        screen_width: int,
        screen_height: int,
        sheet_file_path: str,
        metadata_file_path: str,
        screen_count: int,
        provider: SpritesheetLoopRandomProvider | None = None,
    ) -> None:
        self.screen_width, self.screen_height = screen_width, screen_height
        self.screen_count = screen_count
        self.provider = provider or SpritesheetLoopRandomProvider(
            sheet_file_path=sheet_file_path,
            metadata_file_path=metadata_file_path,
            screen_count=screen_count,
        )

        super().__init__(builder=self.provider)
        self.device_display_mode = DeviceDisplayMode.FULL

    def real_process(
        self,
        window: DisplayContext,
        orientation: Orientation,
    ) -> None:
        state = self.state
        current_phase_frames = self.provider.frames[state.phase]
        current_kf = current_phase_frames[state.current_frame]

        spritesheet = state.spritesheet
        if spritesheet is None:
            return

        scaled = spritesheet.image_at_scaled(
            current_kf.frame, (self.screen_width, self.screen_height)
        )
        window.blit(scaled, (state.current_screen * self.screen_width, 0))

    def state_observable(
        self,
        peripheral_manager: PeripheralManager,
    ) -> reactivex.Observable[SpritesheetLoopRandomState]:
        return self.provider.observable(peripheral_manager=peripheral_manager)
