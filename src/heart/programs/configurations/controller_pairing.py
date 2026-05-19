from heart.renderers.controller_pairing import ControllerPairingRenderer
from heart.runtime.game_loop import GameLoop


def configure(loop: GameLoop) -> None:
    controller_pairing_mode = loop.add_mode("pair bt")
    controller_pairing_mode.add_renderer(ControllerPairingRenderer())
    loop.components.game_modes.state.in_select_mode = False
