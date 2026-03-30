"""Validate spritesheet asset loading across pygame display lifecycle states."""

from heart.assets.loader import Loader
from heart.assets.spritesheet import Spritesheet


class TestSpritesheetLoading:
    """Ensure spritesheet loading works before display setup so scene construction can happen during bootstrap."""

    IMAGE_SIZE = (32, 32)

    def test_loads_without_initialized_display_surface(self) -> None:
        """Verify spritesheets load before `set_mode` so configuration assembly does not crash during startup."""
        spritesheet = Spritesheet(Loader.resolve_path("heart_16_small.png"))

        assert spritesheet.get_size() == self.IMAGE_SIZE

    def test_converts_after_display_surface_exists(self) -> None:
        """Confirm spritesheets still render correctly after display setup so deferred optimization keeps runtime behavior intact."""
        spritesheet = Spritesheet(Loader.resolve_path("heart_16_small.png"))
        surface = spritesheet.image_at((0, 0, *self.IMAGE_SIZE))

        assert surface.get_size() == self.IMAGE_SIZE

        import pygame

        pygame.display.set_mode((1, 1))
        converted = spritesheet.image_at((0, 0, *self.IMAGE_SIZE))

        assert converted.get_size() == self.IMAGE_SIZE
