"""In-memory model of a low-power drawing pad peripheral.

The :class:`DrawingPad` peripheral models a 6"×6" slate that supports a
battery-friendly stylus and a dedicated erase mode.  The implementation keeps
state entirely in-memory so that the rest of the runtime can experiment with the
input vocabulary before we have real hardware.  The backing grid uses a modest
48×48 resolution so updates remain cheap on slower hosts such as microcontrollers
or older Raspberry Pi models.

Each input event is expected to provide a coordinate pair.  Callers can specify
coordinates either as relative values in the ``[0.0, 1.0]`` range or in inches by
setting ``units="inches"``.  A stylus event writes pressure values into the
underlying grid, while an erase event clears a circular region.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Self

import reactivex
from reactivex import operators as ops

from heart.peripheral.core import Input, InputDescriptor, Peripheral


@dataclass(slots=True)
class StylusSample:
    """Snapshot of a stylus interaction on the drawing pad."""

    x: float
    y: float
    pressure: float
    radius: float
    is_erase: bool = False


class DrawingPad(Peripheral[Any]):
    """Virtual 6"×6" drawing surface with stylus and erase support.

    Parameters
    ----------
    width_inches:
        Physical width of the pad.  Defaults to 6 inches.
    height_inches:
        Physical height of the pad.  Defaults to 6 inches.
    resolution:
        Number of discrete cells along each axis.  Higher values increase
        fidelity at the cost of additional memory and CPU when filling regions.
    polling_interval:
        Sleep duration used by :meth:`run` when idling.  The default keeps CPU
        usage negligible on single-board computers.
    """

    WIDTH_INCHES = 6.0
    HEIGHT_INCHES = 6.0
    DEFAULT_RESOLUTION = 48

    def __init__(
        self,
        *,
        width_inches: float | None = None,
        height_inches: float | None = None,
        resolution: int = DEFAULT_RESOLUTION,
        polling_interval: float = 0.1,
    ) -> None:
        if resolution <= 0:
            raise ValueError("resolution must be positive")

        self.width_inches = width_inches or self.WIDTH_INCHES
        self.height_inches = height_inches or self.HEIGHT_INCHES
        if self.width_inches <= 0 or self.height_inches <= 0:
            raise ValueError("physical dimensions must be positive")

        self.resolution = resolution
        self._grid = [
            [0.0 for _ in range(self.resolution)] for _ in range(self.resolution)
        ]
        self._stylus_history: list[StylusSample] = []
        self._polling_interval = polling_interval
        self._stop = threading.Event()
        super().__init__()

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------
    def handle_input(self, input: Input) -> None:  # noqa: D401 - signature fixed
        """Process stylus or erase events and update the backing grid."""

        if input.event_type == "drawing_pad.stroke":
            self._apply_stylus(**self._parse_payload(input.data, is_erase=False))
        elif input.event_type == "drawing_pad.erase":
            self._apply_stylus(**self._parse_payload(input.data, is_erase=True))

    def inputs(
        self,
        *,
        event_bus: reactivex.Observable[Input] | None = None,
    ) -> tuple[InputDescriptor, ...]:
        if event_bus is None:
            raise ValueError("event_bus is required to describe DrawingPad inputs")
        stroke_stream = event_bus.pipe(
            ops.filter(lambda event: event.event_type == "drawing_pad.stroke"),
            ops.map(lambda event: event.data),
        )
        erase_stream = event_bus.pipe(
            ops.filter(lambda event: event.event_type == "drawing_pad.erase"),
            ops.map(lambda event: event.data),
        )
        return (
            InputDescriptor(
                name="drawing_pad.stroke",
                stream=stroke_stream,
                payload_type=dict,
                description=(
                    "Stylus payload with x, y, pressure, radius, and units fields."
                ),
            ),
            InputDescriptor(
                name="drawing_pad.erase",
                stream=erase_stream,
                payload_type=dict,
                description=(
                    "Erase payload with x, y, radius, and units fields."
                ),
            ),
        )

    def apply_stylus(
        self,
        *,
        x: float,
        y: float,
        pressure: float = 1.0,
        radius: float = 0.05,
        units: str = "relative",
    ) -> None:
        """Public helper to draw with the stylus programmatically."""

        payload = {
            "x": x,
            "y": y,
            "pressure": pressure,
            "radius": radius,
            "units": units,
        }
        self._apply_stylus(**self._parse_payload(payload, is_erase=False))

    def erase(
        self,
        *,
        x: float,
        y: float,
        radius: float = 0.1,
        units: str = "relative",
    ) -> None:
        """Erase a circular area centred at ``(x, y)``."""

        payload = {
            "x": x,
            "y": y,
            "radius": radius,
            "units": units,
            "pressure": 0.0,
        }
        self._apply_stylus(**self._parse_payload(payload, is_erase=True))

    def clear(self) -> None:
        """Reset the drawing surface to its blank state."""

        for row in self._grid:
            for idx in range(len(row)):
                row[idx] = 0.0
        self._stylus_history.clear()

    def iter_rows(self) -> Iterable[Iterable[float]]:
        """Yield the grid rows – useful for snapshots in tests."""

        for row in self._grid:
            yield tuple(row)

    def last_sample(self) -> StylusSample | None:
        """Return the most recent stylus interaction, if any."""

        return self._stylus_history[-1] if self._stylus_history else None

    # ------------------------------------------------------------------
    # Detection helpers
    # ------------------------------------------------------------------
    @classmethod
    def detect(cls) -> Iterator[Self]:
        """Expose a single virtual drawing pad instance."""
        yield cls()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _parse_payload(self, data: Mapping[str, Any], *, is_erase: bool) -> dict[str, Any]:
        if "x" not in data or "y" not in data:
            raise ValueError("payload must contain 'x' and 'y'")

        units = data.get("units", "relative")
        x_norm = self._normalize_coordinate(float(data["x"]), units, axis="x")
        y_norm = self._normalize_coordinate(float(data["y"]), units, axis="y")
        radius = float(data.get("radius", 0.05))
        radius_norm = self._normalize_distance(radius, units, axis="x")
        pressure = float(data.get("pressure", 1.0))

        return {
            "sample": StylusSample(
                x=x_norm,
                y=y_norm,
                pressure=pressure,
                radius=radius_norm,
                is_erase=is_erase,
            )
        }

    def _apply_stylus(self, *, sample: StylusSample) -> None:
        centre_x = self._to_index(sample.x)
        centre_y = self._to_index(sample.y)
        radius_cells = max(1, int(round(sample.radius * (self.resolution - 1))))
        affected = self._iter_indices_within_radius(centre_x, centre_y, radius_cells)

        for row_idx, col_idx in affected:
            if sample.is_erase:
                self._grid[row_idx][col_idx] = 0.0
            else:
                self._grid[row_idx][col_idx] = max(
                    0.0, min(1.0, sample.pressure)
                )

        self._stylus_history.append(sample)

    def _normalize_coordinate(self, value: float, units: str, *, axis: str) -> float:
        if units == "relative":
            normalized = value
        elif units == "inches":
            inches = self.width_inches if axis == "x" else self.height_inches
            normalized = value / inches
        else:
            raise ValueError(f"Unsupported units: {units}")

        return max(0.0, min(1.0, normalized))

    def _normalize_distance(self, value: float, units: str, *, axis: str) -> float:
        if units == "relative":
            normalized = value
        elif units == "inches":
            inches = self.width_inches if axis == "x" else self.height_inches
            normalized = value / inches
        else:
            raise ValueError(f"Unsupported units: {units}")

        return max(0.0, normalized)

    def _to_index(self, normalized: float) -> int:
        return int(round(normalized * (self.resolution - 1)))

    def _iter_indices_within_radius(
        self, centre_x: int, centre_y: int, radius_cells: int
    ) -> Iterable[tuple[int, int]]:
        for row_idx in range(
            max(0, centre_y - radius_cells), min(self.resolution, centre_y + radius_cells + 1)
        ):
            for col_idx in range(
                max(0, centre_x - radius_cells),
                min(self.resolution, centre_x + radius_cells + 1),
            ):
                if self._within_radius(centre_x, centre_y, col_idx, row_idx, radius_cells):
                    yield (row_idx, col_idx)

    @staticmethod
    def _within_radius(
        centre_x: int,
        centre_y: int,
        x: int,
        y: int,
        radius: int,
    ) -> bool:
        return (x - centre_x) ** 2 + (y - centre_y) ** 2 <= radius**2
