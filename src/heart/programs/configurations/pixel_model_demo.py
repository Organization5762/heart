"""Configuration wiring for the PixelModelRenderer demo."""

from __future__ import annotations

from pathlib import Path

from heart.display.renderers.pixel_model import PixelModelRenderer
from heart.programs.configurations import base


def build_configuration() -> base.ProgramConfiguration:
    """Register a single mode that runs the PixelModelRenderer."""

    configuration = base.ProgramConfiguration()
    mode = configuration.create_mode("pixel_model")
    model_path = Path("docs/assets/models/pixel_runner.obj")
    mode.add_renderer(
        PixelModelRenderer(
            model_path=str(model_path),
            target_rows=96,
            palette_levels=6,
        )
    )
    return configuration
