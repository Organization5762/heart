from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from PIL import Image, ImageEnhance

from heart.assets.loader import Loader
from heart.renderers.vibe.state import (
    HEART_FRAME_COUNT,
    HEART_FRAME_DURATION_MS,
    HEART_FRAME_SIZE,
    HEART_SHEET_PATH,
    OVERMONO_FRAME_COUNT,
    OVERMONO_FRAME_DURATION_MS,
    OVERMONO_FRAME_SIZE,
    OVERMONO_SHEET_PATH,
    SUN2_BRIGHTNESS,
    SUNSLEEPER2_FRAME_COUNT,
    SUNSLEEPER2_FRAME_DURATION_MS,
    SUNSLEEPER2_FRAME_SIZE,
    SUNSLEEPER2_SHEET_PATH,
    SUN_FRAME_COUNT,
    SUN_FRAME_DURATION_MS,
    SUN_FRAME_SIZE,
    SUN_SHEET_PATH,
)


@dataclass(frozen=True)
class VibeGifSpec:
    sheet_path: Path
    frame_size: int
    frame_count: int
    duration_ms: int
    brightness: float = 1.0


SPECS = {
    "heart": VibeGifSpec(
        sheet_path=HEART_SHEET_PATH,
        frame_size=HEART_FRAME_SIZE,
        frame_count=HEART_FRAME_COUNT,
        duration_ms=HEART_FRAME_DURATION_MS,
    ),
    "overmono": VibeGifSpec(
        sheet_path=OVERMONO_SHEET_PATH,
        frame_size=OVERMONO_FRAME_SIZE,
        frame_count=OVERMONO_FRAME_COUNT,
        duration_ms=OVERMONO_FRAME_DURATION_MS,
    ),
    "sun": VibeGifSpec(
        sheet_path=SUN_SHEET_PATH,
        frame_size=SUN_FRAME_SIZE,
        frame_count=SUN_FRAME_COUNT,
        duration_ms=SUN_FRAME_DURATION_MS,
    ),
    "sun2": VibeGifSpec(
        sheet_path=SUN_SHEET_PATH,
        frame_size=SUN_FRAME_SIZE,
        frame_count=SUN_FRAME_COUNT,
        duration_ms=SUN_FRAME_DURATION_MS,
        brightness=SUN2_BRIGHTNESS,
    ),
    "sunsleeper2": VibeGifSpec(
        sheet_path=SUNSLEEPER2_SHEET_PATH,
        frame_size=SUNSLEEPER2_FRAME_SIZE,
        frame_count=SUNSLEEPER2_FRAME_COUNT,
        duration_ms=SUNSLEEPER2_FRAME_DURATION_MS,
    ),
}


def render_frames(spec: VibeGifSpec) -> list[Image.Image]:
    source = Image.open(Loader.resolve_path(spec.sheet_path)).convert("RGBA")
    frames = []
    for frame_index in range(spec.frame_count):
        left = frame_index * spec.frame_size
        frame = source.crop((left, 0, left + spec.frame_size, spec.frame_size))
        if spec.brightness != 1.0:
            frame = ImageEnhance.Brightness(frame).enhance(spec.brightness)
        frames.append(frame)
    return frames


def save_gif(frames: list[Image.Image], output: Path, duration_ms: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    first_frame, *remaining_frames = frames
    first_frame.save(
        output,
        save_all=True,
        append_images=remaining_frames,
        duration=duration_ms,
        loop=0,
        disposal=2,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Heart vibe spritesheet loops as GIFs for HUB75 testing."
    )
    parser.add_argument("scene", choices=sorted(SPECS))
    parser.add_argument("output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    spec = SPECS[args.scene]
    frames = render_frames(spec)
    save_gif(frames, args.output, spec.duration_ms)
    print(
        f"wrote {args.scene} gif frames={len(frames)} "
        f"duration_ms={spec.duration_ms} path={args.output}"
    )


if __name__ == "__main__":
    main()
