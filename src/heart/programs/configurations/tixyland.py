from typing import Callable

import numpy as np

from heart.navigation import MultiScene
from heart.renderers.tixyland import Tixyland, TixylandFactory
from heart.runtime.game_loop import GameLoop


def pattern_numpy(t: float, X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    t_i = int(t)
    val = (Y - 2 * t_i) * (X - 2 - t_i)
    return val


def configure(loop: GameLoop) -> None:
    tixyland_factory = loop.resolve(TixylandFactory)

    def build_tixyland(
        fn: Callable[[float, np.ndarray, np.ndarray, np.ndarray], np.ndarray]
    ) -> Tixyland:
        return tixyland_factory(fn)

    mode = loop.add_mode()
    mode.add_renderer(
        MultiScene(
            [
                build_tixyland(fn=lambda t, i, x, y: np.sin(y / 8 + t)),
                build_tixyland(fn=lambda t, i, x, y: np.sin(np.ones(x.shape) * t)),
                build_tixyland(fn=lambda t, i, x, y: y - t * t),
                build_tixyland(
                    fn=lambda t, i, x, y: np.sin(
                        t
                        - np.sqrt((x - x.shape[0] / 2) ** 2 + (y - y.shape[1] / 2) ** 2)
                    )
                ),
                build_tixyland(fn=lambda t, i, x, y: np.sin(y / 8 + t)),
                build_tixyland(fn=lambda t, i, x, y: pattern_numpy(t, x, y)),
                build_tixyland(fn=lambda t, i, x, y: np.random.rand(*x.shape) < 0.1),
                build_tixyland(fn=lambda t, i, x, y: np.random.rand(*x.shape)),
            ]
        )
    )
