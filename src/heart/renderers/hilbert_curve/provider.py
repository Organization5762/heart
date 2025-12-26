from __future__ import annotations

import math
import time
from dataclasses import replace

import numpy as np
import reactivex
from numba import njit
from reactivex import operators as ops

from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.core.providers import ObservableProvider
from heart.renderers.hilbert_curve.state import BoundingBox, HilbertCurveState


def compute_bounding_box(points: np.ndarray) -> BoundingBox:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


@njit
def d2xy(n: int, d: int) -> tuple[int, int]:
    x = 0
    y = 0
    t = d
    s = 1
    while s < n:
        rx = (t // 2) & 1
        ry = (t ^ rx) & 1
        if ry == 0:
            if rx == 1:
                x = s - 1 - x
                y = s - 1 - y
            temp = x
            x = y
            y = temp
        x += s * rx
        y += s * ry
        t //= 4
        s *= 2
    return x, y


@njit
def hilbert_curve_points_numba(
    order: int, width: int, height: int, xmargin: int, ymargin: int
) -> np.ndarray:
    n = 2**order
    total_points = n * n

    ymargin = ymargin or xmargin

    draw_size = width - 2 * xmargin if width < height else height - 2 * ymargin
    step = draw_size / (n - 1) if n > 1 else draw_size

    points = np.empty((total_points, 2), dtype=np.float64)
    for d in range(total_points):
        x_grid, y_grid = d2xy(n, d)
        points[d, 0] = xmargin + x_grid * step
        points[d, 1] = ymargin + y_grid * step
    return points


@njit
def resample_curve_numba(points: np.ndarray, num_samples: int) -> np.ndarray:
    n = points.shape[0]
    if n < 2:
        return points

    cumdist = np.empty(n, dtype=np.float64)
    cumdist[0] = 0.0
    for i in range(1, n):
        dx = points[i, 0] - points[i - 1, 0]
        dy = points[i, 1] - points[i - 1, 1]
        cumdist[i] = cumdist[i - 1] + math.hypot(dx, dy)
    total_length = cumdist[n - 1]

    new_points = np.empty((num_samples, 2), dtype=np.float64)
    j = 0
    for i in range(num_samples):
        td = i * total_length / (num_samples - 1)
        while j < n - 1 and cumdist[j + 1] < td:
            j += 1
        if j >= n - 1:
            new_points[i, 0] = points[n - 1, 0]
            new_points[i, 1] = points[n - 1, 1]
        else:
            seg_length = cumdist[j + 1] - cumdist[j]
            t_interp = 0.0
            if seg_length != 0.0:
                t_interp = (td - cumdist[j]) / seg_length
            new_points[i, 0] = points[j, 0] + t_interp * (points[j + 1, 0] - points[j, 0])
            new_points[i, 1] = points[j, 1] + t_interp * (points[j + 1, 1] - points[j, 1])
    return new_points


@njit
def interpolate_curves_numba(curve1: np.ndarray, curve2: np.ndarray, alpha: float) -> np.ndarray:
    n = curve1.shape[0]
    interpolated = np.empty((n, 2), dtype=np.float64)
    for i in range(n):
        interpolated[i, 0] = (1 - alpha) * curve1[i, 0] + alpha * curve2[i, 0]
        interpolated[i, 1] = (1 - alpha) * curve1[i, 1] + alpha * curve2[i, 1]
    return interpolated


@njit
def transform_points(
    points: np.ndarray,
    alpha: float,
    bbox: BoundingBox,
    target_scale: float,
    margin: int,
) -> list[tuple[float, float]]:
    min_x, min_y, _, _ = bbox
    new_points: list[tuple[float, float]] = []
    for p in points:
        p_zoom = (
            (p[0] - min_x) * target_scale + margin,
            (p[1] - min_y) * target_scale + margin,
        )
        new_points.append(
            (
                (1 - alpha) * p[0] + alpha * p_zoom[0],
                (1 - alpha) * p[1] + alpha * p_zoom[1],
            )
        )
    return new_points


class HilbertCurveProvider(ObservableProvider[HilbertCurveState]):
    def __init__(
        self,
        *,
        max_order: int = 7,
        xmargin: int = 0,
        ymargin: int | None = None,
        resample_count: int = 10000,
        morph_duration: float = 0.5,
        hold_duration: float = 0.5,
        zoom_duration: float = 3.0,
        zoom_hold_duration: float = 1.0,
        subset_exponent: int | None = None,
    ) -> None:
        self.max_order = max_order
        self.xmargin = xmargin
        self.ymargin = ymargin if ymargin is not None else xmargin
        self.resample_count = resample_count
        self.morph_duration = morph_duration
        self.hold_duration = hold_duration
        self.zoom_duration = zoom_duration
        self.zoom_hold_duration = zoom_hold_duration
        self.subset_exponent = subset_exponent or (max_order + 4)

    def initial_state(self, *, width: int, height: int) -> HilbertCurveState:
        current_order = 1
        next_order = current_order + 1
        base_points = hilbert_curve_points_numba(
            current_order, width, height, self.xmargin, self.ymargin
        )
        current_curve = resample_curve_numba(base_points, self.resample_count)
        next_points = hilbert_curve_points_numba(
            next_order, width, height, self.xmargin, self.ymargin
        )
        target_curve = resample_curve_numba(next_points, self.resample_count)
        now = time.monotonic()
        return HilbertCurveState(
            width=width,
            height=height,
            xmargin=self.xmargin,
            ymargin=self.ymargin,
            resample_count=self.resample_count,
            max_order=self.max_order,
            current_order=current_order,
            next_order=next_order,
            current_curve=current_curve,
            target_curve=target_curve,
            next_points=next_points,
            transition_state="morph",
            morph_start_time=now,
            zoom_start_time=None,
            zoom_bbox=None,
            target_scale=None,
            frame_curve=current_curve,
        )

    def _advance_morph(self, state: HilbertCurveState, now: float) -> HilbertCurveState:
        elapsed = now - state.morph_start_time
        alpha = min(1.0, elapsed / self.morph_duration)
        frame_curve = interpolate_curves_numba(state.current_curve, state.target_curve, alpha)

        hold_duration = self.hold_duration if state.current_order < self.max_order - 2 else 0
        if alpha < 1.0 or elapsed < self.morph_duration + hold_duration:
            return replace(state, frame_curve=frame_curve)

        if state.next_order == self.max_order:
            zoom_bbox = compute_bounding_box(
                frame_curve[: len(frame_curve) // (2**self.subset_exponent)]
            )
            draw_size = min(state.width, state.height) - (2 * state.xmargin)
            bbox_width = zoom_bbox[2] - zoom_bbox[0]
            bbox_height = zoom_bbox[3] - zoom_bbox[1]
            target_scale = (draw_size * 2) / max(bbox_width, bbox_height)
            return replace(
                state,
                transition_state="zoom",
                zoom_start_time=now,
                zoom_bbox=zoom_bbox,
                target_scale=target_scale,
                frame_curve=frame_curve,
            )

        current_order = state.next_order
        next_order = current_order + 1
        next_points = hilbert_curve_points_numba(
            next_order, state.width, state.height, state.xmargin, state.ymargin
        )
        target_curve = resample_curve_numba(next_points, state.resample_count)
        return replace(
            state,
            current_order=current_order,
            next_order=next_order,
            current_curve=frame_curve,
            next_points=next_points,
            target_curve=target_curve,
            morph_start_time=now,
            frame_curve=frame_curve,
        )

    def _advance_zoom(self, state: HilbertCurveState, now: float) -> HilbertCurveState:
        assert state.zoom_start_time is not None
        assert state.zoom_bbox is not None
        assert state.target_scale is not None

        zoom_elapsed = now - state.zoom_start_time
        raw_alpha = min(zoom_elapsed / self.zoom_duration, 1.0)
        zoom_alpha = -0.5 * (math.cos(math.pi * raw_alpha) - 1)

        zoomed_curve = transform_points(
            hilbert_curve_points_numba(
                state.max_order, state.width, state.height, state.xmargin, state.ymargin
            ),
            zoom_alpha,
            state.zoom_bbox,
            state.target_scale,
            state.xmargin,
        )

        if zoom_elapsed < self.zoom_duration + self.zoom_hold_duration:
            return replace(state, frame_curve=np.array(zoomed_curve))

        return self.initial_state(width=state.width, height=state.height)

    def advance(self, state: HilbertCurveState, *, now: float) -> HilbertCurveState:
        if state.transition_state == "zoom":
            return self._advance_zoom(state, now)
        return self._advance_morph(state, now)

    def observable(
        self,
        peripheral_manager: PeripheralManager,
    ) -> reactivex.Observable[HilbertCurveState]:
        window_sizes = peripheral_manager.window.pipe(
            ops.filter(lambda window: window is not None),
            ops.map(lambda window: window.get_size()),
            ops.distinct_until_changed(),
        )

        def build_stream(
            size: tuple[int, int],
        ) -> reactivex.Observable[HilbertCurveState]:
            initial_state = self.initial_state(width=size[0], height=size[1])
            return peripheral_manager.game_tick.pipe(
                ops.filter(lambda tick: tick is not None),
                ops.map(lambda _: time.monotonic()),
                ops.scan(
                    lambda state, now: self.advance(state, now=now),
                    seed=initial_state,
                ),
                ops.start_with(initial_state),
            )

        return window_sizes.pipe(
            ops.map(build_stream),
            ops.switch_latest(),
            ops.share(),
        )
