from __future__ import annotations

from heart.display.color import Color
from heart.display.renderers import BaseRenderer
from heart.display.renderers.artist.state import ArtistState
from heart.display.renderers.image import RenderImage
from heart.display.renderers.sliding_image import SlidingImage
from heart.display.renderers.spritesheet import SpritesheetLoop
from heart.display.renderers.text import TextRendering
from heart.display.renderers.yolisten import YoListenRenderer


class ArtistStateProvider:
    def build(self) -> ArtistState:
        scenes: list[BaseRenderer] = []

        for artist in [
            "imaginal_disk_animated",
            "rainbow_tesseract",
            "dancing_robot",
            "jamie_xx_life",
            "john_summit_neon",
            "troyboi_glitch_cartwheel",
        ]:
            scenes.append(
                SpritesheetLoop(
                    sheet_file_path=f"artist/{artist}.png",
                    metadata_file_path=f"artist/{artist}.json",
                    boomerang=(artist != "troyboi_glitch_cartwheel"),
                )
            )

        for artist in [
            "jamie_xx_in_color",
        ]:
            scenes.append(
                SpritesheetLoop.from_frame_data(
                    sheet_file_path=f"artist/{artist}.png",
                    duration=75,
                    boomerang=False,
                    skip_last_frame=True,
                )
            )

        scenes.append(
            SlidingImage(
                image_file="artist/virji_spritesheet.png",
                speed=1,
            )
        )

        scenes.append(YoListenRenderer())
        return ArtistState(scenes=scenes)

    @staticmethod
    def title_renderers() -> list[BaseRenderer]:
        return [
            RenderImage(image_file="artist/imaginal_disk.png"),
            TextRendering(
                text=["artist"],
                font="Roboto",
                font_size=14,
                color=Color(255, 105, 180),
                y_location=32,
            ),
        ]
