"""Configuration wiring for the PixelModelRenderer demo."""

from __future__ import annotations

from heart.display.renderers.pixel_model import PixelModelRenderer
from heart.programs.configurations import base
from heart.utilities.paths import docs_asset_path


def build_configuration() -> base.ProgramConfiguration:
    """Register a single mode that runs the PixelModelRenderer."""

    configuration = base.ProgramConfiguration()
    mode = configuration.create_mode("pixel_model")
    model_path = docs_asset_path("models", "pixel_runner.obj")
    mode.add_renderer(
        PixelModelRenderer(
            model_path=model_path,
            target_rows=96,
            palette_levels=6,
        )
    )
    return configuration
