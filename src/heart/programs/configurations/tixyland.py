import numpy as np

from heart.display.renderers.tixyland import Tixyland
from heart.environment import GameLoop
from heart.navigation import MultiScene



def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.add_renderer(
        MultiScene(
            [
                Tixyland(fn=lambda t, i, x, y: np.sin(y / 8 + t)),
                Tixyland(fn=lambda t, i, x, y: np.sin(np.ones(x.shape) * t)),
                Tixyland(fn=lambda t, i, x, y: y - t * t),
                Tixyland(
                    fn=lambda t, i, x, y: np.sin(
                        t
                        - np.sqrt((x - x.shape[0] / 2) ** 2 + (y - y.shape[1] / 2) ** 2)
                    )
                ),
                Tixyland(fn=lambda t, i, x, y: np.sin(y / 8 + t)),
                Tixyland(fn=lambda t, i, x, y: pattern_numpy(t, x, y)),
                Tixyland(fn=lambda t, i, x, y: np.random.rand(*x.shape) < 0.1),
                Tixyland(fn=lambda t, i, x, y: np.random.rand(*x.shape)),
            ]
        )
    )
