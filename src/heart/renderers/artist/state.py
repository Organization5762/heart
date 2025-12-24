from dataclasses import dataclass
from pathlib import Path

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
            sheet_path = Path("artist") / f"{artist}.png"
            metadata_path = Path("artist") / f"{artist}.json"
            scenes.append(
                SpritesheetLoop(
                    sheet_file_path=str(sheet_path),
                    metadata_file_path=str(metadata_path),
                    boomerang=(artist != "troyboi_glitch_cartwheel"),
                )
            )

        for artist in [
            "jamie_xx_in_color",
        ]:
            sheet_path = Path("artist") / f"{artist}.png"
            scenes.append(
                SpritesheetLoop.from_frame_data(
                    sheet_file_path=str(sheet_path),
                    duration=75,
                    boomerang=False,
                    skip_last_frame=True,
                )
            )

        scenes.append(
            SlidingImage(
                image_file=str(Path("artist") / "virji_spritesheet.png"),
                speed=1,
            )
        )

        scenes.append(YoListenRenderer())
        return ArtistState(scenes=scenes)
