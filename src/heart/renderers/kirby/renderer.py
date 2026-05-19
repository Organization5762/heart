from heart.display.color import Color
from heart.navigation import MultiScene
from heart.peripheral.core.input import GamepadController
from heart.renderers import StatefulBaseRenderer
from heart.renderers.kirby.state import KirbyState
from heart.renderers.spritesheet import SpritesheetLoop
from heart.renderers.text import TextRendering


class KirbyScene(MultiScene):
    def __init__(self) -> None:
        kirby_state = KirbyState.build()
        super().__init__(kirby_state.scenes)
        self._last_dpad_x = 0

    def reset(self) -> None:
        self._last_dpad_x = 0
        super().reset()

    def get_renderers(self) -> list[StatefulBaseRenderer]:
        self._process_dpad_scene_selection()
        return super().get_renderers()

    def _process_dpad_scene_selection(self) -> None:
        # Kirby can be warmup-reset before ComposedRenderer flattens it again.
        # The old state still carries the peripheral manager, so read from it
        # even when initialized is false.
        if self._state is None or not self.scenes:
            return
        peripheral_manager = self.state.peripheral_manager
        if peripheral_manager is None:
            return
        gamepad = peripheral_manager.get_gamepad()
        if gamepad is None or not gamepad.is_connected():
            self._last_dpad_x = 0
            return
        mapping = GamepadController._mapping_for_gamepad(gamepad)
        dpad = GamepadController._read_dpad(gamepad, mapping)
        direction = int(dpad.x)
        if direction == self._last_dpad_x:
            return
        self._last_dpad_x = direction
        if direction == 0:
            return
        previous_index = self._active_scene_index()
        self.state.current_button_value += direction
        next_index = self._active_scene_index()
        if previous_index != next_index:
            self.scenes[previous_index].reset()
            self._last_active_scene_index = next_index

    @staticmethod
    def title_scene() -> list[StatefulBaseRenderer]:
        return [
            SpritesheetLoop(
                sheet_file_path="kirby_flying_32.png",
                metadata_file_path="kirby_flying_32.json",
                image_scale=1 / 3,
                offset_y=-5,
                disable_input=True,
            ),
            TextRendering(
                text=["kirby mode"],
                font="Grand9K Pixel.ttf",
                font_size=12,
                color=Color.kirby(),
                y_location=0.65,
            ),
        ]
