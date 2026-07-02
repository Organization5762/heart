"""Render an approximate HUB75 image from a Saleae raw digital CSV.

This decodes each LAT rise as a row commit. For every commit, it samples the
last N clocked data bits before LAT, maps them through the RGB top/bottom pins,
and accumulates a virtual image. When --weight-oe is set, each commit is weighted
by the following active-low OE pulse duration, which approximates PWM brightness.
"""

from __future__ import annotations

import argparse
import csv
from bisect import bisect_right
from dataclasses import dataclass
from statistics import median
from pathlib import Path


DEFAULT_CONNECTOR_MAP = {
    "R1": 0,
    "B1": 1,
    "R2": 2,
    "B2": 3,
    "A": 4,
    "C": 5,
    "CLK": 6,
    "OE": 7,
    "G1": 8,
    "LAT": 9,
    "D": 10,
    "B": 11,
    "G2": 13,
}


@dataclass(frozen=True)
class Capture:
    initial: list[int]
    edges: dict[int, list[float]]
    rises: dict[int, list[float]]
    falls: dict[int, list[float]]
    first_timestamp: float
    last_timestamp: float

    def level_at_channel(self, channel: int, timestamp: float) -> int:
        return self.initial[channel] ^ (
            bisect_right(self.edges[channel], timestamp) & 1
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--cols", type=int, default=128)
    parser.add_argument("--rows", type=int, default=64)
    parser.add_argument("--sample-before-ns", type=float, default=1.0)
    parser.add_argument("--weight-oe", action="store_true")
    parser.add_argument(
        "--normalize",
        choices=("weighted", "max-channel", "dominant"),
        default="weighted",
        help="weighted averages sampled brightness; max-channel removes per-pixel brightness; dominant keeps only the strongest channel.",
    )
    parser.add_argument("--reverse-x", action="store_true")
    parser.add_argument("--auto-offset-red-green", action="store_true")
    parser.add_argument("--separate-half-offsets", action="store_true")
    parser.add_argument("--offset-min", type=int, default=-64)
    parser.add_argument("--offset-max", type=int, default=64)
    parser.add_argument("--offset-step", type=int, default=1)
    parser.add_argument("--min-offset-score", type=float, default=0.0)
    parser.add_argument("--skip-commits", type=int, default=0)
    parser.add_argument("--max-commits", type=int, default=0)
    parser.add_argument(
        "--signal",
        action="append",
        default=[],
        metavar="NAME=CHANNEL",
        help="Override signal channel, e.g. --signal CLK=6.",
    )
    args = parser.parse_args()

    signal_map = DEFAULT_CONNECTOR_MAP | parse_signal_overrides(args.signal)
    capture = load_capture(args.csv, max(signal_map.values()) + 1)
    image, stats = decode_virtual_image(
        capture,
        signal_map,
        cols=args.cols,
        rows=args.rows,
        sample_before_seconds=args.sample_before_ns / 1_000_000_000,
        weight_oe=args.weight_oe,
        normalize=args.normalize,
        reverse_x=args.reverse_x,
        auto_offset_red_green=args.auto_offset_red_green,
        separate_half_offsets=args.separate_half_offsets,
        offset_min=args.offset_min,
        offset_max=args.offset_max,
        offset_step=args.offset_step,
        min_offset_score=args.min_offset_score,
        skip_commits=args.skip_commits,
        max_commits=args.max_commits,
    )
    write_ppm(args.out, image)
    print_summary(args.out, stats)
    return 0


def parse_signal_overrides(overrides: list[str]) -> dict[str, int]:
    parsed: dict[str, int] = {}
    for override in overrides:
        name, separator, value = override.partition("=")
        if not separator:
            raise SystemExit(f"invalid --signal {override!r}; expected NAME=CHANNEL")
        parsed[name.strip().upper()] = int(value.strip(), 0)
    return parsed


def load_capture(path: Path, channel_count: int) -> Capture:
    edges = {channel: [] for channel in range(channel_count)}
    rises = {channel: [] for channel in range(channel_count)}
    falls = {channel: [] for channel in range(channel_count)}
    initial: list[int] | None = None
    previous: list[int] | None = None
    first_timestamp = 0.0
    last_timestamp = 0.0

    with path.open(newline="") as handle:
        rows = csv.reader(handle)
        next(rows)
        for row in rows:
            timestamp = float(row[0])
            state = [int(value) for value in row[1 : 1 + channel_count]]
            if initial is None:
                initial = state.copy()
                first_timestamp = timestamp
            if previous is not None:
                for channel, (old, new) in enumerate(zip(previous, state, strict=True)):
                    if old == new:
                        continue
                    edges[channel].append(timestamp)
                    if new:
                        rises[channel].append(timestamp)
                    else:
                        falls[channel].append(timestamp)
            previous = state
            last_timestamp = timestamp

    if initial is None:
        raise SystemExit(f"{path}: empty capture")
    return Capture(initial, edges, rises, falls, first_timestamp, last_timestamp)


def decode_virtual_image(
    capture: Capture,
    signal_map: dict[str, int],
    *,
    cols: int,
    rows: int,
    sample_before_seconds: float,
    weight_oe: bool,
    normalize: str,
    reverse_x: bool,
    auto_offset_red_green: bool,
    separate_half_offsets: bool,
    offset_min: int,
    offset_max: int,
    offset_step: int,
    min_offset_score: float,
    skip_commits: int,
    max_commits: int,
) -> tuple[list[list[list[float]]], dict[str, object]]:
    half_rows = rows // 2
    accum = [[[0.0, 0.0, 0.0] for _ in range(cols)] for _ in range(rows)]
    weight_accum = [[0.0 for _ in range(cols)] for _ in range(rows)]
    clk_rises = capture.rises[signal_map["CLK"]]
    lat_rises = capture.rises[signal_map["LAT"]]
    used_commits = 0
    skipped_short = 0
    skipped_address = 0
    skipped_score = 0
    offset_counts: dict[int, int] = {}
    top_offset_counts: dict[int, int] = {}
    bottom_offset_counts: dict[int, int] = {}
    offset_scores: list[float] = []
    first_used_lat = None
    last_used_lat = None

    for lat_index, lat_time in enumerate(lat_rises):
        if lat_index < skip_commits:
            continue
        if max_commits and used_commits >= max_commits:
            break
        base_clock_end = bisect_right(clk_rises, lat_time - sample_before_seconds)
        top_offset = 0
        bottom_offset = 0
        score = 0.0
        if auto_offset_red_green:
            top_offset, top_score = best_red_green_offset(
                capture,
                signal_map,
                clk_rises,
                base_clock_end,
                cols=cols,
                sample_before_seconds=sample_before_seconds,
                offset_min=offset_min,
                offset_max=offset_max,
                offset_step=offset_step,
                half="top",
            )
            if separate_half_offsets:
                bottom_offset, bottom_score = best_red_green_offset(
                    capture,
                    signal_map,
                    clk_rises,
                    base_clock_end,
                    cols=cols,
                    sample_before_seconds=sample_before_seconds,
                    offset_min=offset_min,
                    offset_max=offset_max,
                    offset_step=offset_step,
                    half="bottom",
                )
                score = min(top_score, bottom_score)
            else:
                bottom_offset = top_offset
                score = top_score
            if score < min_offset_score:
                skipped_score += 1
                continue
            offset_counts[top_offset] = offset_counts.get(top_offset, 0) + 1
            top_offset_counts[top_offset] = top_offset_counts.get(top_offset, 0) + 1
            bottom_offset_counts[bottom_offset] = (
                bottom_offset_counts.get(bottom_offset, 0) + 1
            )
            offset_scores.append(score)
            clock_end = base_clock_end + top_offset
        else:
            clock_end = base_clock_end
            bottom_offset = 0
        clock_start = clock_end - cols
        bottom_clock_end = base_clock_end + bottom_offset
        bottom_clock_start = bottom_clock_end - cols
        if clock_start < 0:
            skipped_short += 1
            continue
        if bottom_clock_start < 0:
            skipped_short += 1
            continue
        clocks = clk_rises[clock_start:clock_end]
        bottom_clocks = clk_rises[bottom_clock_start:bottom_clock_end]
        row = row_address_at(capture, signal_map, lat_time - sample_before_seconds)
        if row >= half_rows:
            skipped_address += 1
            continue
        weight = (
            oe_weight_after_lat(capture, signal_map, lat_time) if weight_oe else 1.0
        )
        if weight <= 0:
            continue
        for shifted_x, clock_time in enumerate(clocks):
            x = cols - 1 - shifted_x if reverse_x else shifted_x
            sample_time = clock_time - sample_before_seconds
            top = (
                capture.level_at_channel(signal_map["R1"], sample_time),
                capture.level_at_channel(signal_map["G1"], sample_time),
                capture.level_at_channel(signal_map["B1"], sample_time),
            )
            add_pixel(accum, weight_accum, x, row, top, weight)
        for shifted_x, clock_time in enumerate(bottom_clocks):
            x = cols - 1 - shifted_x if reverse_x else shifted_x
            sample_time = clock_time - sample_before_seconds
            bottom = (
                capture.level_at_channel(signal_map["R2"], sample_time),
                capture.level_at_channel(signal_map["G2"], sample_time),
                capture.level_at_channel(signal_map["B2"], sample_time),
            )
            add_pixel(accum, weight_accum, x, row + half_rows, bottom, weight)
        used_commits += 1
        first_used_lat = lat_time if first_used_lat is None else first_used_lat
        last_used_lat = lat_time

    image = normalize_image(accum, weight_accum, normalize)
    stats = {
        "used_commits": used_commits,
        "skipped_short": skipped_short,
        "skipped_address": skipped_address,
        "skipped_score": skipped_score,
        "offset_counts": dict(sorted(offset_counts.items())),
        "top_offset_counts": dict(sorted(top_offset_counts.items())),
        "bottom_offset_counts": dict(sorted(bottom_offset_counts.items())),
        "median_offset_score": median(offset_scores) if offset_scores else None,
        "first_used_lat": first_used_lat,
        "last_used_lat": last_used_lat,
        "weight_oe": weight_oe,
        "normalize": normalize,
        "reverse_x": reverse_x,
        "separate_half_offsets": separate_half_offsets,
    }
    return image, stats


def best_red_green_offset(
    capture: Capture,
    signal_map: dict[str, int],
    clk_rises: list[float],
    base_clock_end: int,
    *,
    cols: int,
    sample_before_seconds: float,
    offset_min: int,
    offset_max: int,
    offset_step: int,
    half: str,
) -> tuple[int, float]:
    best_offset = 0
    best_score = float("-inf")
    if offset_step <= 0:
        raise SystemExit("--offset-step must be > 0")
    for offset in range(offset_min, offset_max + 1, offset_step):
        clock_end = base_clock_end + offset
        clock_start = clock_end - cols
        if clock_start < 0 or clock_end > len(clk_rises):
            continue
        clocks = clk_rises[clock_start:clock_end]
        score = red_green_pattern_score(
            capture,
            signal_map,
            clocks,
            sample_before_seconds,
            half=half,
        )
        if score > best_score:
            best_score = score
            best_offset = offset
    return best_offset, best_score


def red_green_pattern_score(
    capture: Capture,
    signal_map: dict[str, int],
    clocks: list[float],
    sample_before_seconds: float,
    half: str,
) -> float:
    split = len(clocks) // 2
    if split == 0:
        return float("-inf")
    first = clocks[:split]
    second = clocks[split:]
    if half == "top":
        red_signal = "R1"
        green_signal = "G1"
        blue_signal = "B1"
    elif half == "bottom":
        red_signal = "R2"
        green_signal = "G2"
        blue_signal = "B2"
    else:
        raise SystemExit(f"unknown half {half!r}")
    r_first = channel_sum(capture, signal_map[red_signal], first, sample_before_seconds)
    r_second = channel_sum(
        capture, signal_map[red_signal], second, sample_before_seconds
    )
    g_first = channel_sum(
        capture, signal_map[green_signal], first, sample_before_seconds
    )
    g_second = channel_sum(
        capture, signal_map[green_signal], second, sample_before_seconds
    )
    b_total = channel_sum(
        capture, signal_map[blue_signal], clocks, sample_before_seconds
    )

    expected = r_first + g_second
    unexpected = r_second + g_first + b_total
    total = expected + unexpected
    if total == 0:
        return 0.0
    return (expected - unexpected) / total


def channel_sum(
    capture: Capture,
    channel: int,
    clocks: list[float],
    sample_before_seconds: float,
) -> int:
    edges = capture.edges[channel]
    initial = capture.initial[channel]
    return sum(
        initial ^ (bisect_right(edges, clock - sample_before_seconds) & 1)
        for clock in clocks
    )


def row_address_at(
    capture: Capture, signal_map: dict[str, int], timestamp: float
) -> int:
    value = 0
    for bit, signal in enumerate(("A", "B", "C", "D", "E")):
        channel = signal_map.get(signal)
        if channel is not None and capture.level_at_channel(channel, timestamp):
            value |= 1 << bit
    return value


def oe_weight_after_lat(
    capture: Capture, signal_map: dict[str, int], lat_time: float
) -> float:
    oe = signal_map["OE"]
    falls = capture.falls[oe]
    rises = capture.rises[oe]
    enable_index = bisect_right(falls, lat_time)
    if enable_index >= len(falls):
        return 0.0
    start = falls[enable_index]
    disable_index = bisect_right(rises, start)
    if disable_index >= len(rises):
        return 0.0
    end = rises[disable_index]
    return max(0.0, end - start)


def add_pixel(
    accum: list[list[list[float]]],
    weight_accum: list[list[float]],
    x: int,
    y: int,
    rgb: tuple[int, int, int],
    weight: float,
) -> None:
    for channel, value in enumerate(rgb):
        accum[y][x][channel] += value * weight
    weight_accum[y][x] += weight


def normalize_image(
    accum: list[list[list[float]]],
    weight_accum: list[list[float]],
    mode: str,
) -> list[list[list[float]]]:
    image = [[[0.0, 0.0, 0.0] for _ in row] for row in accum]
    for y, row in enumerate(accum):
        for x, rgb in enumerate(row):
            weight = weight_accum[y][x]
            if weight <= 0:
                continue
            weighted = [value / weight for value in rgb]
            if mode == "weighted":
                image[y][x] = weighted
                continue
            peak = max(weighted)
            if peak <= 0:
                continue
            if mode == "max-channel":
                image[y][x] = [value / peak for value in weighted]
                continue
            if mode == "dominant":
                dominant_channel = weighted.index(peak)
                image[y][x][dominant_channel] = 1.0
                continue
            raise SystemExit(f"unknown normalize mode {mode!r}")
    return image


def write_ppm(path: Path, image: list[list[list[float]]]) -> None:
    height = len(image)
    width = len(image[0]) if height else 0
    with path.open("wb") as handle:
        handle.write(f"P6\n{width} {height}\n255\n".encode())
        for row in image:
            for rgb in row:
                handle.write(
                    bytes(max(0, min(255, round(value * 255))) for value in rgb)
                )


def print_summary(path: Path, stats: dict[str, object]) -> None:
    print(f"wrote={path}")
    for key, value in stats.items():
        print(f"{key}={value}")


if __name__ == "__main__":
    raise SystemExit(main())
