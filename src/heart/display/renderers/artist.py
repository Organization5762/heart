from heart.display.color import Color
from heart.display.renderers import BaseRenderer
from heart.display.renderers.image import RenderImage
from heart.display.renderers.sliding_image import SlidingImage, SlidingRenderer
from heart.display.renderers.spritesheet import SpritesheetLoop
from heart.display.renderers.text import TextRendering
from heart.display.renderers.yolisten import YoListenRenderer
from heart.navigation import MultiScene


class ArtistScene(MultiScene):
    def __init__(self) -> None:
        scenes: list[BaseRenderer] = []

        # Two animated sprite sheets
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
                    # Assumes the loop begins and ends on the same
                    skip_last_frame=True,
                )
            )

        # And one sliding banner that wraps around all 4 faces
        scenes.append(
            SlidingImage(
                image_file="artist/virji_spritesheet.png",
                speed=1,
            )
        )

        scenes.append(YoListenRenderer())

        super().__init__(scenes)

    @staticmethod
    def title_scene() -> list[BaseRenderer]:
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
