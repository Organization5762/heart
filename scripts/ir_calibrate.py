"""CLI utilities for calibrating the IR sensor array peripheral."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import requests
import typer

from heart.peripheral.ir_sensor_array import SPEED_OF_LIGHT, radial_layout

app = typer.Typer(help="Calibrate IR sensor arrays from captured sweep data.")

DEFAULT_OUTPUT_PATH = Path("ir_array_offsets.json")
DEFAULT_LAYOUT = "radial"
DEFAULT_LAYOUT_FILE = None
DEFAULT_PROPAGATION_SPEED = SPEED_OF_LIGHT
DEFAULT_TELEMETRY_URL = None


@dataclass(slots=True)
class CaptureRecord:
    frame_id: int
    sensor_index: int
    timestamp: float
    true_position: tuple[float, float, float]


def _load_records(path: Path) -> list[CaptureRecord]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    try:
        loaded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Failed to parse {path}: {exc}") from exc

    if isinstance(loaded, dict) and "records" in loaded:
        loaded = loaded["records"]

    if not isinstance(loaded, list):
        raise typer.BadParameter(f"Expected a list of records in {path}")

    records: list[CaptureRecord] = []
    for idx, entry in enumerate(loaded):
        if not isinstance(entry, dict):
            raise typer.BadParameter(f"Record {idx} is not a mapping")
        try:
            frame_id = int(entry["frame_id"])
            sensor_index = int(entry["sensor_index"])
            timestamp = float(entry["timestamp"])
            true_position = tuple(float(v) for v in entry["true_position"])
        except (KeyError, TypeError, ValueError) as exc:
            raise typer.BadParameter(f"Malformed record at index {idx}: {exc}") from exc
        if len(true_position) != 3:
            raise typer.BadParameter(
                f"Record {idx} true_position must have three coordinates"
            )
        records.append(
            CaptureRecord(
                frame_id=frame_id,
                sensor_index=sensor_index,
                timestamp=timestamp,
                true_position=true_position,
            )
        )
    return records


def _resolve_layout(layout: str, layout_file: Path | None) -> np.ndarray:
    if layout_file is not None:
        data = json.loads(layout_file.read_text(encoding="utf-8"))
        if not isinstance(data, (list, tuple)):
            raise typer.BadParameter("Layout file must contain a list of positions")
        return np.asarray(data, dtype=float)

    layout = layout.lower()
    if layout == "radial":
        return np.asarray(radial_layout(), dtype=float)
    raise typer.BadParameter(f"Unknown layout '{layout}'")


def _group_by_frame(records: Iterable[CaptureRecord]) -> dict[int, dict[int, CaptureRecord]]:
    frames: dict[int, dict[int, CaptureRecord]] = {}
    for record in records:
        frames.setdefault(record.frame_id, {})[record.sensor_index] = record
    return frames


def _compute_offsets(
    frames: dict[int, dict[int, CaptureRecord]],
    sensor_positions: np.ndarray,
    *,
    propagation_speed: float,
) -> tuple[dict[int, float], dict[str, float]]:
    offsets: dict[int, list[float]] = {}
    residuals: list[float] = []
    frames_used = 0

    for frame_id, sensors in frames.items():
        if len(sensors) != sensor_positions.shape[0]:
            continue

        true_position = None
        for record in sensors.values():
            true_position = record.true_position
            break
        assert true_position is not None
        target = np.asarray(true_position, dtype=float)

        for sensor_index, record in sensors.items():
            sensor_pos = sensor_positions[sensor_index]
            expected = np.linalg.norm(target - sensor_pos) / propagation_speed
            offset = record.timestamp - expected
            offsets.setdefault(sensor_index, []).append(offset)
            residuals.append(offset)

        frames_used += 1

    collapsed = {
        sensor: float(np.median(values))
        for sensor, values in offsets.items()
        if values
    }

    rmse = float(np.sqrt(np.mean(np.square(residuals)))) if residuals else 0.0
    max_offset = float(max(abs(value) for value in residuals)) if residuals else 0.0

    metrics = {
        "frames_used": float(frames_used),
        "rmse": rmse,
        "max_offset": max_offset,
    }
    return collapsed, metrics


@app.command()
def calibrate(
    data: Path = typer.Argument(..., help="Path to captured sweep data (JSON)."),
    output: Path = typer.Option(
        DEFAULT_OUTPUT_PATH,
        "--output",
        "-o",
        help="Destination for calibration offsets (JSON).",
    ),
    layout: str = typer.Option(DEFAULT_LAYOUT, help="Built-in sensor layout to use."),
    layout_file: Path | None = typer.Option(
        DEFAULT_LAYOUT_FILE,
        help="Optional path to custom sensor layout JSON overriding --layout.",
    ),
    propagation_speed: float = typer.Option(
        DEFAULT_PROPAGATION_SPEED,
        help="Propagation speed for the burst medium (m/s).",
    ),
    telemetry_url: str | None = typer.Option(
        DEFAULT_TELEMETRY_URL,
        help="Optional HTTP endpoint that receives the calibration payload.",
    ),
) -> None:
    """Solve calibration offsets for each sensor channel."""

    records = _load_records(data)
    if not records:
        raise typer.BadParameter("No records found in capture file")

    sensor_positions = _resolve_layout(layout, layout_file)
    frames = _group_by_frame(records)
    offsets, metrics = _compute_offsets(
        frames, sensor_positions, propagation_speed=propagation_speed
    )

    payload = {"offsets": offsets, "metrics": metrics}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    typer.echo(f"Wrote calibration to {output}")

    if telemetry_url:
        try:
            response = requests.post(telemetry_url, json=payload, timeout=5)
            response.raise_for_status()
        except requests.RequestException as exc:  # pragma: no cover - network
            raise typer.BadParameter(f"Telemetry upload failed: {exc}") from exc
        typer.echo(f"Uploaded calibration to {telemetry_url}")


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    app()
