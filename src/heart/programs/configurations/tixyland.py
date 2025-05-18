import numpy as np
from heart.environment import GameLoop
from heart.display.renderers.tixyland import Tixyland
from heart.navigation import MultiScene

def configure(loop: GameLoop) -> None:
    mode = loop.add_mode()
    mode.add_renderer(
        MultiScene(
            [
                # Tixyland(
                #     fn=lambda t, i, x, y: np.sin(y / 8 + t)
                # ),
                # Tixyland(
                #     fn=lambda t, i, x, y: np.random.rand(*x.shape) < 0.1
                # ),
                # Tixyland(
                #     fn=lambda t, i, x, y: np.random.rand(*x.shape)
                # ),
                Tixyland(
                    fn=lambda t, i, x, y: np.sin(np.ones(x.shape) * t)
                ),
                Tixyland(
                    fn=lambda t, i, x, y: y - t * t
                ),
                Tixyland(
                    fn=lambda t, i, x, y: np.sin(t - np.sqrt((x - x.shape[0] / 2) ** 2 + (y - y.shape[1] / 2) ** 2))
                ),
                Tixyland(
                    fn=lambda t, i, x, y: np.sin(y/8 + t)
                ),
                Tixyland(
                    fn=lambda t, i, x, y: (y-4*t|0) * (x-2-t|0)
                ),
                # Tixyland(
                #     fn=lambda t, i, x, y: 4 * t & i & x & y
                # )
            ]
        )
    )
    # mode.add_renderer(
    #     Tixyland(
    #         fn=lambda t, i, x, y: np.random() < 0.1
    #     )
    # )
    # mode.add_renderer(
    #     Tixyland(
    #         fn=lambda t, i, x, y: np.random()
    #     )
    # )
    # mode.add_renderer(
    #     Tixyland(
    #         fn=lambda t, i, x, y: np.sin(t)
    #     )
    # )
    # mode.add_renderer(
    #     Tixyland(
    #         fn=lambda t, i, x, y: y - t
    #     ),
    #     Tixyland(
    #         fn=lambda t, i, x, y: y - t * t
    #     ),
    #     Tixyland(
    #         fn=lambda t, i, x, y: np.sin(t - np.sqrt((x - 7.5) ** 2 + (y - 6) ** 2))
    #     ),
    #     Tixyland(
    #         fn=lambda t, i, x, y: np.sin(y/8 + t)
    #     ),
    #     Tixyland(
    #         fn=lambda t, i, x, y: -(x>t & y>t & x<15-t & y<15-t)
    #     ),
    #     Tixyland(
    #         fn=lambda t, i, x, y: (y-4*t|0) * (x-2-t|0)
    #     ),
    #     Tixyland(
    #         fn=lambda t, i, x, y: 4 * t & i & x & y
    #     )
    # )