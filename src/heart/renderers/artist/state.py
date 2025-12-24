from dataclasses import dataclass

from heart.renderers import StatefulBaseRenderer
from heart.renderers.sliding_image import SlidingImage
from heart.renderers.spritesheet import SpritesheetLoop
from heart.renderers.yolisten import YoListenRenderer


@dataclass
class ArtistState:
    scenes: list[StatefulBaseRenderer]

    @staticmethod
    def build() -> "ArtistState":
        scenes: list[StatefulBaseRenderer] = []

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
