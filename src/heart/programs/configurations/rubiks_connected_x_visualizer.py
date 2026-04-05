from heart.display.color import Color
from heart.renderers.color import RenderColor
from heart.renderers.rubiks_connected_x_visualizer import (
    RubiksConnectedXVisualizerRenderer,
)
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode(
        loop.compose(
            [
                RenderColor(Color(0, 0, 0)),
                RubiksConnectedXVisualizerRenderer(),
            ]
        )
    )
    mode.add_renderer(RenderColor(Color(0, 0, 0)))
    mode.add_renderer(RubiksConnectedXVisualizerRenderer())
    loop.components.game_modes.state._active_mode_index = 0
    loop.components.game_modes.state.mode_offset = 0
    loop.components.game_modes.state.in_select_mode = False
