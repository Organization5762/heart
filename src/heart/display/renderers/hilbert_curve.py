import math
import time

import numpy as np
import pygame
from numba import njit

from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.environment import DeviceDisplayMode
from heart.peripheral.core.manager import PeripheralManager


class HilbertScene(BaseRenderer):
    def __init__(self):
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self.width = None
        self.height = None
        self.FPS = 60
        self.max_order = 7
        self.xmargin = 0
        self.ymargin = 0
        self.resample_count = 10000  # Number of points to use for interpolation.
        self.morph_duration = 0.5  # Seconds for the morph transition.
        self.hold_duration = 0.5  # Hold time after morph completes.

        self.base_points: np.ndarray | None = None
        self.base_curve = None
        self.current_order = 1
        self.current_curve = None
        self.next_order = None
        self.next_points = None
        self.target_curve = None
        self.morph_start_time = None
        self.transition_state = "morph"

        self.zoom_duration = 3.0
        self.zoom_hold_duration = 1.0
        self.subset_exponent = self.max_order + 4
        self.zoom_start_time = None
        self.zoom_bbox = None
        self.target_scale = None

        self.forwards = True

        self.background_color = (0, 0, 0)
        self.line_color = (215, 72, 148)

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        self.width = window.get_width()
        self.height = window.get_height()
        self.base_points = hilbert_curve_points_numba(
            self.current_order, self.width, self.height, self.xmargin, self.ymargin
        )
        self.current_curve = resample_curve_numba(self.base_points, self.resample_count)
        self.next_order = self.current_order + 1
        self.next_points = hilbert_curve_points_numba(
            self.next_order, self.width, self.height, self.xmargin, self.ymargin
        )
        self.target_curve = resample_curve_numba(self.next_points, self.resample_count)
        self.morph_start_time = time.time()
        super().initialize(window, clock, peripheral_manager, orientation)

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ):
        # set bg
        window.fill((0, 0, 0))

        curr_time = time.time()
        if self.transition_state == "morph":
            elapsed = time.time() - self.morph_start_time
            if elapsed < self.morph_duration:
                alpha = elapsed / self.morph_duration
            else:
                alpha = 1.0

            morphed_curve = interpolate_curves_numba(
                self.current_curve, self.target_curve, alpha
            )
            if len(morphed_curve) > 1:
                pygame.draw.lines(window, self.line_color, False, morphed_curve, 1)

            # if self.next_order == self.max_order:
            #     self.forwards = False
            # elif self.next_order == 1:
            #     self.forwards = True

            # hack to "skip" the hold at order=7, we want an odd max-order to have the symmetric loop
            # but the resolution we're at fills out the screen already order=6
            hold_duration = (
                self.hold_duration if self.current_order < self.max_order - 2 else 0
            )

            if alpha >= 1.0 and elapsed >= self.morph_duration + hold_duration:
                if self.next_order == self.max_order:
                    self.transition_state = "zoom"
                    self.zoom_start_time = time.time()

                    subset = self.current_curve[
                        : len(self.current_curve) // (2 ** (self.subset_exponent))
                    ]
                    self.zoom_bbox = compute_bounding_box(subset)
                    # Compute the drawing area.
                    draw_size = min(self.width, self.height) - (2 * self.xmargin)
                    bbox_min_x, bbox_min_y, bbox_max_x, bbox_max_y = self.zoom_bbox
                    bbox_width = bbox_max_x - bbox_min_x
                    bbox_height = bbox_max_y - bbox_min_y
                    # For uniform scaling, choose the factor that maps the larger bbox dimension to draw_size.
                    self.target_scale = (draw_size * 2) / max(bbox_width, bbox_height)
                else:
                    self.current_order = self.next_order
                    self.next_order = self.current_order + 1
                    self.current_curve = self.target_curve
                    self.next_points = hilbert_curve_points_numba(
                        self.next_order,
                        self.width,
                        self.height,
                        self.xmargin,
                        self.ymargin,
                    )
                    self.target_curve = resample_curve_numba(
                        self.next_points, self.resample_count
                    )
                    self.morph_start_time = curr_time

        elif self.transition_state == "zoom":
            zoom_elapsed = curr_time - self.zoom_start_time
            raw_alpha = min(zoom_elapsed / self.zoom_duration, 1.0)
            # Use an easing function to adjust the zoom interpolation.
            # zoom_alpha = raw_alpha * raw_alpha * (3 - 2 * raw_alpha)  # Cubic ease in/out
            # Alternatively, uncomment the following two lines to use cosine ease:
            zoom_alpha = -0.5 * (math.cos(math.pi * raw_alpha) - 1)

            zoomed_curve = transform_points(
                hilbert_curve_points_numba(
                    self.max_order, self.width, self.height, self.xmargin, self.ymargin
                ),
                zoom_alpha,
                self.zoom_bbox,
                self.target_scale,
                self.xmargin,
            )
            if len(zoomed_curve) > 1:
                pygame.draw.lines(window, self.line_color, False, zoomed_curve, 2)

            if zoom_elapsed >= self.zoom_duration + self.zoom_hold_duration:
                self.current_order = 1
                self.next_order = 2
                self.base_points = hilbert_curve_points_numba(
                    self.current_order,
                    self.width,
                    self.height,
                    self.xmargin,
                    self.ymargin,
                )
                self.current_curve = resample_curve_numba(
                    self.base_points, self.resample_count
                )
                self.next_points = hilbert_curve_points_numba(
                    self.next_order, self.width, self.height, self.xmargin, self.ymargin
                )
                self.target_curve = resample_curve_numba(
                    self.next_points, self.resample_count
                )
                self.morph_start_time = curr_time
                self.transition_state = "morph"

            # self.current_order = self.next_order
            # self.current_curve = self.target_curve
            # self.next_order = self.current_order + 1 if self.forwards else self.current_order - 1
            # self.next_points = hilbert_curve_points_numba(
            #     self.next_order, self.width, self.height, self.xmargin, self.ymargin
            # )
            # self.target_curve = resample_curve_numba(self.next_points, self.resample_count)
            # self.morph_start_time = time.time()

        # font = pygame.font.SysFont("Arial", 20)
        # text = font.render(f"Hilbert Curve Order: {self.current_order}", True, (220, 220, 220))
        # window.blit(text, (10, self.height - 30))

        # pygame.display.flip()


def compute_bounding_box(points):
    """Compute the bounding box (min_x, min_y, max_x, max_y) for a list of points."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


@njit
def d2xy(n, d):
    """Convert a one-dimensional index 'd' to 2D (x,y) coordinates on an n x n grid
    using the Hilbert curve algorithm."""
    x = 0
    y = 0
    t = d
    s = 1
    while s < n:
        # Using bitwise operations for efficiency.
        rx = (t // 2) & 1
        ry = (t ^ rx) & 1
        if ry == 0:
            if rx == 1:
                x = s - 1 - x
                y = s - 1 - y
            # Swap x and y
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
    order: int, width: int, height: int, xmargin: int, ymargin: int = None
):
    """Generate Hilbert curve points as a numpy array (N x 2) scaled to fit inside a
    square area defined by the window size."""
    n = 2**order
    total_points = n * n

    ymargin = ymargin or xmargin

    # Determine the drawing square (using the smaller dimension).
    if width < height:
        draw_size = width - 2 * xmargin
    else:
        draw_size = height - 2 * ymargin
    # Compute the step size (distance between grid points).
    step = draw_size / (n - 1) if n > 1 else draw_size

    # Preallocate numpy array for (x,y) positions.
    points = np.empty((total_points, 2), dtype=np.float64)
    for d in range(total_points):
        x_grid, y_grid = d2xy(n, d)
        points[d, 0] = xmargin + x_grid * step
        points[d, 1] = ymargin + y_grid * step
    return points


@njit
def resample_curve_numba(points, num_samples):
    """Given a numpy array of points defining a polyline, resample the curve so that it
    has exactly num_samples points, evenly spaced by arc length."""
    n = points.shape[0]
    if n < 2:
        return points
    # Compute cumulative distances.
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
            new_points[i, 0] = points[j, 0] + t_interp * (
                points[j + 1, 0] - points[j, 0]
            )
            new_points[i, 1] = points[j, 1] + t_interp * (
                points[j + 1, 1] - points[j, 1]
            )
    return new_points


@njit
def interpolate_curves_numba(curve1, curve2, alpha):
    """Given two curves (numpy arrays of shape (N,2)), interpolate between them.

    When alpha is 0, returns curve1; when alpha is 1, returns curve2.

    """
    n = curve1.shape[0]
    interpolated = np.empty((n, 2), dtype=np.float64)
    for i in range(n):
        interpolated[i, 0] = (1 - alpha) * curve1[i, 0] + alpha * curve2[i, 0]
        interpolated[i, 1] = (1 - alpha) * curve1[i, 1] + alpha * curve2[i, 1]
    return interpolated


@njit
def transform_points(points, alpha, bbox, target_scale, margin):
    """Interpolate between identity transformation and a zoom transform. At alpha=0,
    each point is unchanged.

    At alpha=1, each point p is transformed as:
         p_new = ( (p - (bbox_min)) * target_scale ) + (margin, margin)

    """
    min_x, min_y, _, _ = bbox
    new_points = []
    for p in points:
        # Identity part: leave p unchanged.
        p_identity = p
        # Zoomed part: shift so that bbox minimum becomes 0, then scale, then add margin.
        p_zoom = (
            (p[0] - min_x) * target_scale + margin,
            (p[1] - min_y) * target_scale + margin,
        )
        new_points.append(
            (
                (1 - alpha) * p_identity[0] + alpha * p_zoom[0],
                (1 - alpha) * p_identity[1] + alpha * p_zoom[1],
            )
        )

    return new_points
