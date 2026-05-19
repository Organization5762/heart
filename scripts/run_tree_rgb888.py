"""Stream the tree spritesheet into the raw RP1 PIO RGB888 test buffer."""

from __future__ import annotations

import argparse
import mmap
import os
import struct
import time
from pathlib import Path
from typing import Final

from PIL import Image, ImageEnhance

RP1_SRAM_HOST_BASE: Final[int] = 0x1F00400000
RP1_SRAM_MAP_SIZE: Final[int] = 0x10000
DEFAULT_OFFSET: Final[int] = 0xC000
DEFAULT_SECONDS: Final[float] = 300.0
DEFAULT_FRAME_MS: Final[float] = 67.0
DEFAULT_SOURCE_FRAME_SIZE: Final[int] = 384
DEFAULT_PANEL_SIZE: Final[int] = 64
DEFAULT_CROP_MODE: Final[str] = "center"
CROP_MODE_CHOICES: Final[tuple[str, ...]] = ("center", "top-left")
ROWPAIRS: Final[int] = 32
COLS: Final[int] = 64
FRAME_BYTES: Final[int] = ROWPAIRS * COLS * 2 * 4
DEFAULT_TREE_SHEET: Final[Path] = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "heart"
    / "assets"
    / "vibe"
    / "tree_384x384_spritesheet.png"
)


def main() -> int:
    args = parse_args()
    frames = load_rgb888_frames(
        args.sheet,
        source_frame_size=args.source_frame_size,
        panel_size=args.panel_size,
        brightness=args.brightness,
        contrast=args.contrast,
        saturation=args.saturation,
        gamma=args.gamma,
        nearest=args.nearest,
        scale=args.scale,
        crop_mode=args.crop_mode,
        crop_x=args.crop_x,
        crop_y=args.crop_y,
    )
    if not frames:
        raise SystemExit(f"No frames loaded from {args.sheet}")
    if args.dry_run:
        print(
            f"tree-rgb888 dry-run frames={len(frames)} "
            f"bytes_per_frame={len(frames[0])} sheet={args.sheet}",
            flush=True,
        )
        return 0

    deadline = time.monotonic() + args.seconds
    frame_interval = args.frame_ms / 1000.0
    updates = 0
    frame_index = 0

    fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)
    try:
        memory = mmap.mmap(
            fd,
            RP1_SRAM_MAP_SIZE,
            flags=mmap.MAP_SHARED,
            prot=mmap.PROT_READ | mmap.PROT_WRITE,
            offset=RP1_SRAM_HOST_BASE,
        )
    finally:
        os.close(fd)

    try:
        next_frame_time = time.monotonic()
        while time.monotonic() < deadline:
            memory[args.offset : args.offset + FRAME_BYTES] = frames[frame_index]
            updates += 1
            if updates == 1 or updates % 60 == 0:
                print(
                    "tree-rgb888 "
                    f"update={updates} frame={frame_index} "
                    f"frames={len(frames)} frame_ms={args.frame_ms:.3f} "
                    f"brightness={args.brightness:.3f} "
                    f"contrast={args.contrast:.3f} "
                    f"saturation={args.saturation:.3f} gamma={args.gamma:.3f}",
                    flush=True,
                )
            frame_index = (frame_index + 1) % len(frames)
            next_frame_time += frame_interval
            sleep_seconds = next_frame_time - time.monotonic()
            if sleep_seconds > 0:
                time.sleep(sleep_seconds)
            else:
                next_frame_time = time.monotonic()
    finally:
        memory.close()

    print(
        f"tree-rgb888 done updates={updates} seconds={args.seconds:.3f}",
        flush=True,
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write the tree spritesheet into the RP1 RGB888 source buffer."
    )
    parser.add_argument("--sheet", type=Path, default=DEFAULT_TREE_SHEET)
    parser.add_argument("--seconds", type=float, default=DEFAULT_SECONDS)
    parser.add_argument("--frame-ms", type=float, default=DEFAULT_FRAME_MS)
    parser.add_argument("--offset", type=parse_int, default=DEFAULT_OFFSET)
    parser.add_argument("--source-frame-size", type=int, default=DEFAULT_SOURCE_FRAME_SIZE)
    parser.add_argument("--panel-size", type=int, default=DEFAULT_PANEL_SIZE)
    parser.add_argument("--brightness", type=float, default=1.0)
    parser.add_argument("--contrast", type=float, default=1.0)
    parser.add_argument("--saturation", type=float, default=1.0)
    parser.add_argument("--gamma", type=float, default=1.0)
    parser.add_argument("--nearest", action="store_true")
    scale_group = parser.add_mutually_exclusive_group()
    scale_group.add_argument("--scale", dest="scale", action="store_true", default=True)
    scale_group.add_argument("--crop", dest="scale", action="store_false")
    parser.add_argument("--crop-mode", choices=CROP_MODE_CHOICES, default=DEFAULT_CROP_MODE)
    parser.add_argument("--crop-x", type=int)
    parser.add_argument("--crop-y", type=int)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def parse_int(value: str) -> int:
    return int(value, 0)


def load_rgb888_frames(
    sheet_path: Path,
    *,
    source_frame_size: int,
    panel_size: int,
    brightness: float,
    contrast: float,
    saturation: float,
    gamma: float,
    nearest: bool,
    scale: bool,
    crop_mode: str,
    crop_x: int | None,
    crop_y: int | None,
) -> list[bytes]:
    sheet = Image.open(sheet_path).convert("RGB")
    frame_count = sheet.width // source_frame_size
    resample = Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS
    return [
        pack_frame(
            prepare_frame_image(
                sheet,
                frame_index=frame_index,
                source_frame_size=source_frame_size,
                panel_size=panel_size,
                scale=scale,
                crop_mode=crop_mode,
                crop_x=crop_x,
                crop_y=crop_y,
                resample=resample,
            ),
            brightness=brightness,
            contrast=contrast,
            saturation=saturation,
            gamma=gamma,
        )
        for frame_index in range(frame_count)
    ]


def prepare_frame_image(
    sheet: Image.Image,
    *,
    frame_index: int,
    source_frame_size: int,
    panel_size: int,
    scale: bool,
    crop_mode: str,
    crop_x: int | None,
    crop_y: int | None,
    resample: Image.Resampling,
) -> Image.Image:
    source = sheet.crop(
        (
            frame_index * source_frame_size,
            0,
            (frame_index + 1) * source_frame_size,
            source_frame_size,
        )
    )
    if scale:
        return source.resize((panel_size, panel_size), resample)

    left, top = crop_origin(
        source_frame_size=source_frame_size,
        panel_size=panel_size,
        crop_mode=crop_mode,
        crop_x=crop_x,
        crop_y=crop_y,
    )
    return source.crop((left, top, left + panel_size, top + panel_size))


def crop_origin(
    *,
    source_frame_size: int,
    panel_size: int,
    crop_mode: str,
    crop_x: int | None,
    crop_y: int | None,
) -> tuple[int, int]:
    max_origin = source_frame_size - panel_size
    if max_origin < 0:
        raise ValueError(
            f"Cannot crop {panel_size}x{panel_size} from {source_frame_size}x{source_frame_size}"
        )

    if crop_mode == "top-left":
        left = 0
        top = 0
    else:
        left = max_origin // 2
        top = max_origin // 2

    if crop_x is not None:
        left = crop_x
    if crop_y is not None:
        top = crop_y

    return clamp_crop_origin(left, max_origin), clamp_crop_origin(top, max_origin)


def clamp_crop_origin(value: int, max_origin: int) -> int:
    return max(0, min(max_origin, value))


def pack_frame(
    image: Image.Image,
    *,
    brightness: float,
    contrast: float,
    saturation: float,
    gamma: float,
) -> bytes:
    if image.size != (COLS, ROWPAIRS * 2):
        raise ValueError(f"Expected {COLS}x{ROWPAIRS * 2} image, got {image.size}")

    image = adjust_image(
        image,
        contrast=contrast,
        saturation=saturation,
        gamma=gamma,
    )
    pixels = image.load()
    frame = bytearray(FRAME_BYTES)
    offset = 0
    for row in range(ROWPAIRS):
        for col in range(COLS):
            for y in (row, row + ROWPAIRS):
                r, g, b = pixels[col, y]
                word = (
                    scale_u8(r, brightness)
                    | (scale_u8(g, brightness) << 8)
                    | (scale_u8(b, brightness) << 16)
                )
                struct.pack_into("<I", frame, offset, word)
                offset += 4
    return bytes(frame)


def scale_u8(value: int, brightness: float) -> int:
    return max(0, min(255, int(value * brightness + 0.5)))


def adjust_image(
    image: Image.Image,
    *,
    contrast: float,
    saturation: float,
    gamma: float,
) -> Image.Image:
    adjusted = ImageEnhance.Contrast(image).enhance(contrast)
    adjusted = ImageEnhance.Color(adjusted).enhance(saturation)
    if gamma == 1.0:
        return adjusted

    gamma_exponent = max(gamma, 0.001)
    lookup = [
        max(0, min(255, int(((value / 255.0) ** gamma_exponent) * 255.0 + 0.5)))
        for value in range(256)
    ]
    return adjusted.point(lookup * 3)


if __name__ == "__main__":
    raise SystemExit(main())
