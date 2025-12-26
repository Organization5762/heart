import os

from heart.utilities.env.enums import MandelbrotInteriorStrategy

DEFAULT_MANDELBROT_INTERIOR_STRATEGY = MandelbrotInteriorStrategy.CARDIOID


class MandelbrotConfiguration:
    @classmethod
    def mandelbrot_interior_strategy(cls) -> MandelbrotInteriorStrategy:
        strategy = os.environ.get(
            "HEART_MANDELBROT_INTERIOR_STRATEGY",
            DEFAULT_MANDELBROT_INTERIOR_STRATEGY.value,
        ).strip()
        try:
            return MandelbrotInteriorStrategy(strategy.lower())
        except ValueError as exc:
            raise ValueError(
                "HEART_MANDELBROT_INTERIOR_STRATEGY must be 'none' or 'cardioid'"
            ) from exc
