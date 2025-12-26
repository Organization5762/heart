from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Iterable, Sequence

DEFAULT_AXIS_TOLERANCE_RATIO = 0.6
DEFAULT_PERIMETER_VERTEX_COUNT = 4


@dataclass(frozen=True)
class Point3D:
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class BoundingBox3D:
    min_point: Point3D
    max_point: Point3D

    def center(self) -> Point3D:
        return Point3D(
            x=(self.min_point.x + self.max_point.x) / 2,
            y=(self.min_point.y + self.max_point.y) / 2,
            z=(self.min_point.z + self.max_point.z) / 2,
        )

    def size(self) -> Point3D:
        return Point3D(
            x=self.max_point.x - self.min_point.x,
            y=self.max_point.y - self.min_point.y,
            z=self.max_point.z - self.min_point.z,
        )


@dataclass(frozen=True)
class ColoredBoundingBox:
    color: tuple[int, int, int]
    bounds: BoundingBox3D


@dataclass(frozen=True)
class Layout:
    columns: int
    rows: int
    perimeter: tuple[Point3D, ...]


@dataclass(frozen=True)
class Orientation:
    layout: Layout
    led_positions: tuple[Point3D, ...]


def derive_layout_from_boxes(
    boxes: Sequence[ColoredBoundingBox],
    *,
    axis_tolerance_ratio: float = DEFAULT_AXIS_TOLERANCE_RATIO,
) -> Layout:
    axis_positions = _derive_axis_positions(boxes, axis_tolerance_ratio)
    perimeter = _derive_perimeter(boxes)
    return Layout(
        columns=len(axis_positions.x_positions),
        rows=len(axis_positions.y_positions),
        perimeter=perimeter,
    )


def derive_orientation_from_boxes(
    boxes: Sequence[ColoredBoundingBox],
    *,
    axis_tolerance_ratio: float = DEFAULT_AXIS_TOLERANCE_RATIO,
) -> Orientation:
    axis_positions = _derive_axis_positions(boxes, axis_tolerance_ratio)
    perimeter = _derive_perimeter(boxes)
    layout = Layout(
        columns=len(axis_positions.x_positions),
        rows=len(axis_positions.y_positions),
        perimeter=perimeter,
    )
    ordered_positions = _order_led_positions(boxes, axis_positions)
    return Orientation(layout=layout, led_positions=ordered_positions)


@dataclass(frozen=True)
class _AxisPositions:
    x_positions: tuple[float, ...]
    y_positions: tuple[float, ...]
    z_reference: float


def _derive_axis_positions(
    boxes: Sequence[ColoredBoundingBox],
    axis_tolerance_ratio: float,
) -> _AxisPositions:
    if not boxes:
        raise ValueError("Expected at least one bounding box to derive layout.")

    centers = [box.bounds.center() for box in boxes]
    sizes = [box.bounds.size() for box in boxes]
    tolerance = _calculate_axis_tolerance(sizes, axis_tolerance_ratio)

    x_positions = _cluster_positions([center.x for center in centers], tolerance)
    y_positions = _cluster_positions([center.y for center in centers], tolerance)
    z_reference = median(center.z for center in centers)
    return _AxisPositions(
        x_positions=tuple(x_positions),
        y_positions=tuple(y_positions),
        z_reference=z_reference,
    )


def _calculate_axis_tolerance(
    sizes: Iterable[Point3D],
    axis_tolerance_ratio: float,
) -> float:
    dimensions = [min(size.x, size.y) for size in sizes]
    if not dimensions:
        return 0.0
    return median(dimensions) * axis_tolerance_ratio


def _cluster_positions(values: Iterable[float], tolerance: float) -> list[float]:
    sorted_values = sorted(values)
    if not sorted_values:
        return []

    clusters: list[list[float]] = [[sorted_values[0]]]
    for value in sorted_values[1:]:
        if abs(value - clusters[-1][-1]) <= tolerance:
            clusters[-1].append(value)
        else:
            clusters.append([value])

    return [sum(cluster) / len(cluster) for cluster in clusters]


def _derive_perimeter(boxes: Sequence[ColoredBoundingBox]) -> tuple[Point3D, ...]:
    if not boxes:
        raise ValueError("Expected bounding boxes to derive a perimeter polygon.")

    min_x = min(box.bounds.min_point.x for box in boxes)
    max_x = max(box.bounds.max_point.x for box in boxes)
    min_y = min(box.bounds.min_point.y for box in boxes)
    max_y = max(box.bounds.max_point.y for box in boxes)
    z_reference = median(box.bounds.center().z for box in boxes)

    perimeter = (
        Point3D(min_x, min_y, z_reference),
        Point3D(max_x, min_y, z_reference),
        Point3D(max_x, max_y, z_reference),
        Point3D(min_x, max_y, z_reference),
    )
    if len(perimeter) != DEFAULT_PERIMETER_VERTEX_COUNT:
        raise ValueError("Unexpected perimeter vertex count.")
    return perimeter


def _order_led_positions(
    boxes: Sequence[ColoredBoundingBox],
    axis_positions: _AxisPositions,
) -> tuple[Point3D, ...]:
    placements: list[tuple[int, int, Point3D]] = []
    for box in boxes:
        center = box.bounds.center()
        row = _closest_axis_index(center.y, axis_positions.y_positions)
        column = _closest_axis_index(center.x, axis_positions.x_positions)
        placements.append((row, column, center))

    placements.sort(key=lambda placement: (placement[0], placement[1]))
    return tuple(position for _, _, position in placements)


def _closest_axis_index(value: float, positions: Sequence[float]) -> int:
    if not positions:
        raise ValueError("No axis positions available for layout derivation.")
    distances = [abs(value - position) for position in positions]
    return distances.index(min(distances))
