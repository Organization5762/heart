import cProfile
import dataclasses
import io
import itertools
import os
import pstats
import time

import numpy as np
import pygame
from numba import jit, prange

from heart import DeviceDisplayMode
from heart.device import Cube, Orientation, Rectangle
from heart.peripheral.core.manager import PeripheralManager
from heart.peripheral.gamepad import GamepadIdentifier
from heart.renderers import StatefulBaseRenderer
from heart.renderers.mandelbrot.control_mappings import (KeyboardControls,
                                                         SceneControlsMapping)
from heart.renderers.mandelbrot.controls import SceneControls
from heart.renderers.mandelbrot.state import AppState, ViewMode
from heart.utilities.env import Configuration
from heart.utilities.env.enums import MandelbrotInteriorStrategy
from heart.utilities.logging import get_logger

ColorPalette = list[tuple[int, int, int]]
logger = get_logger(__name__)


class MandelbrotMode(StatefulBaseRenderer[AppState]):
    def __init__(self):
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.FULL
        self.clock: pygame.time.Clock | None = None

        # screen properties
        self.width: int | None = None
        self.height: int | None = None
        self.individual_screen_width: int | None = None
        self.individual_screen_height: int | None = None
        self.screens: dict[tuple[int, int], pygame.Surface] = {}
        self.palettes = self._generate_palettes()
        self.palette_arrays = [
            np.array(palette, dtype=np.uint8) for palette in self.palettes
        ]

        # cache properties for computed converge times for current view port
        self.cached_result = None
        self.last_params = None
        self.cached_julia_result = None
        self.last_julia_params = None

        # auto-zoom loop properties
        self.max_auto_zoom = 20093773861.78
        self.init_zoom = 1
        self.init_offset_x, self.init_offset_y = (
            -0.7446419526560056,
            0.11883810795259032,
        )
        # input properties
        self.time_initialized = None
        # self.gamepad = None
        self.scene_controls: SceneControls | None = None
        self.control_mappings: dict[GamepadIdentifier, SceneControlsMapping] | None = (
            None
        )
        self.keyboard_controls: KeyboardControls | None = None
        self.input_error: bool = False
        self.mandelbrot_interior_strategy = (
            Configuration.mandelbrot_interior_strategy()
        )
        self.use_mandelbrot_interior = (
            self.mandelbrot_interior_strategy == MandelbrotInteriorStrategy.CARDIOID
        )

    def _create_initial_state(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> AppState:
        pygame.font.init()
        self.time_initialized = time.monotonic()
        self.font = pygame.font.SysFont("monospace", 8)
        self.clock = clock
        self.height = window.get_height()
        self.width = window.get_width()
        screen_cols = orientation.layout.columns
        screen_rows = orientation.layout.rows
        self.screens = {
            (i, j): pygame.Surface(
                (self.width // screen_cols, self.height // screen_rows), pygame.SRCALPHA
            )
            for i in range(screen_rows)
            for j in range(screen_cols)
        }
        self.individual_screen_width = self.screens[(0, 0)].get_width()
        self.individual_screen_height = self.screens[(0, 0)].get_height()

        state = AppState(
            movement=pygame.Vector2(self.init_offset_x, self.init_offset_y),
            jmovement=pygame.Vector2(0, 0),
            cursor_pos=pygame.Vector2(0, 0),
            jcursor_pos=pygame.Vector2(0, 0),
            zoom=self.init_zoom,
            max_iterations=250,
            msurface_width=self.width,
            msurface_height=self.height,
            num_palettes=len(self.palettes),
            init_orientation=orientation,
            mode="auto",
        )
        self.set_state(state)
        # self.gamepad = peripheral_manager.get_gamepad()
        self.scene_controls = SceneControls(state)
        self.keyboard_controls = KeyboardControls(self.scene_controls)
        # self.control_mappings = {
        #     GamepadIdentifier.BIT_DO_LITE_2: BitDoLite2Controls(
        #         self.scene_controls, self.gamepad
        #     ),
        #     GamepadIdentifier.SWITCH_PRO: SwitchProControls(
        #         self.scene_controls, self.gamepad
        #     ),
        # }

        if isinstance(orientation, Cube):
            # warmup compilation of the jitted functions
            mandelbrot_surface = pygame.Surface((self.width // 2, self.height))
            julia_surface = pygame.Surface((self.width // 2, self.height))
            self._draw_split_view(mandelbrot_surface, julia_surface, clock)
        return state

    @property
    def active_palette(self):
        return self.palettes[self.state.palette_index]

    @property
    def active_palette_array(self) -> np.ndarray:
        return self.palette_arrays[self.state.palette_index]

    def reset(self):
        self.initialized = False
        # if self.state is not None:
        #     self.state.reset()
        #     self.state.set_mode_auto()

    def process_input(self) -> bool:
        # when we first enter the scene, ignore input for a bit
        if time.monotonic() - self.time_initialized < 0.5:
            return False

        self.keyboard_controls.update()
        # if connected := self.gamepad.is_connected():
        #     mapping = self.control_mappings.get(self.gamepad.gamepad_identifier)
        #     mapping.update()
        return False

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        try:
            gamepad_connected = self.process_input()
            if not gamepad_connected:
                if not self.input_error:
                    self.reset()
                    self.state.set_mode_auto()
            self.input_error = not gamepad_connected
        except Exception as e:
            logger.exception("Error processing input; resetting. %s", e)
            if not self.input_error:
                self.reset()
                self.state.set_mode_auto()
                self.input_error = True

        individual_screen_width = self.screens[(0, 0)].get_width()
        individual_screen_height = self.screens[(0, 0)].get_height()
        if self.state.view_mode == ViewMode.MANDELBROT:
            match self.state.orientation:
                case Rectangle():
                    self._draw_mandelbrot_to_surface(window, clock)
                case Cube():
                    for (x, y), screen in self.screens.items():
                        self._draw_mandelbrot_to_surface(screen, clock)
                        window.blit(
                            screen,
                            (y * individual_screen_width, x * individual_screen_height),
                        )
        elif self.state.view_mode in (
            ViewMode.MANDELBROT_SELECTED,
            ViewMode.JULIA_SELECTED,
        ):
            match self.state.orientation:
                case Rectangle():
                    mandelbrot_surface = pygame.Surface((self.width // 2, self.height))
                    julia_surface = pygame.Surface((self.width // 2, self.height))
                    self._draw_split_view(mandelbrot_surface, julia_surface, clock)
                    # self._draw_orbit_to_surface(mandelbrot_surface)
                    window.blit(mandelbrot_surface, (0, 0))
                    window.blit(julia_surface, (self.width // 2, 0))
                case Cube():
                    screen0 = self.screens[(0, 0)]
                    screen1 = self.screens[(0, 1)]
                    screen2 = self.screens[(0, 2)]
                    screen3 = self.screens[(0, 3)]
                    self._draw_split_view(screen0, screen1, clock)
                    self._draw_split_view(screen2, screen3, clock)
                    window.blit(screen0, (0, 0))
                    window.blit(screen1, (individual_screen_width, 0))
                    window.blit(screen2, (individual_screen_width * 2, 0))
                    window.blit(screen3, (individual_screen_width * 3, 0))
        elif self.state.view_mode == ViewMode.JULIA:
            match self.state.orientation:
                case Rectangle():
                    self._draw_julia_to_surface(window, clock)
                case Cube():
                    for (x, y), screen in self.screens.items():
                        self._draw_julia_to_surface(screen, clock)
                        window.blit(
                            screen,
                            (y * individual_screen_width, x * individual_screen_height),
                        )

        if self.state.show_fps:
            match self.state.orientation:
                case Rectangle():
                    self._draw_fps_to_surface(window)
                case Cube():
                    screen_width = self.screens[(0, 0)].get_width()
                    screen_height = self.screens[(0, 0)].get_height()
                    for (x, y), screen in self.screens.items():
                        self._draw_fps_to_surface(screen)
                        window.blit(screen, (y * screen_width, x * screen_height))

        if self.state.show_debug:
            # debug can just go across the whole window
            self._draw_debug_to_surface(window)

        if self.state.mode == "auto":
            self.auto_zoom()

    def auto_zoom(self):
        self.state.zoom *= 1.05
        if self.state.zoom >= self.max_auto_zoom:
            self.state.zoom = 2**-5
            self.state.max_iterations = self.state._init_max_iterations
        elif self.state.zoom < 2**-5:
            self.state.zoom = 100000000

    def _draw_cursor_to_surface(
        self, surface: pygame.Surface, posx: int, posy: int, cursor_size: float
    ):
        pygame.draw.circle(surface, (0, 0, 0), (posx, posy), 2)
        pygame.draw.circle(surface, (255, 255, 255), (posx, posy), 1)

    def clipped_line_end(self, start, end, screen_rect):
        """Given start=(x0,y0) inside screen_rect, and end=(x1,y1) anywhere, return the
        point where the ray start→end intersects screen_rect."""
        x0, y0 = start
        x1, y1 = end
        dx = x1 - x0
        dy = y1 - y0

        t_candidates = []

        # Avoid division by zero; only consider edges for which the ray is not parallel
        # 1) left edge: x = screen_rect.left
        if dx != 0:
            t = (screen_rect.left - x0) / dx
            y = y0 + t * dy
            if t > 0 and screen_rect.top <= y <= screen_rect.bottom:
                t_candidates.append(t)

            # 2) right edge: x = screen_rect.right
            t = (screen_rect.right - x0) / dx
            y = y0 + t * dy
            if t > 0 and screen_rect.top <= y <= screen_rect.bottom:
                t_candidates.append(t)

        # 3) top edge: y = screen_rect.top
        if dy != 0:
            t = (screen_rect.top - y0) / dy
            x = x0 + t * dx
            if t > 0 and screen_rect.left <= x <= screen_rect.right:
                t_candidates.append(t)

            # 4) bottom edge: y = screen_rect.bottom
            t = (screen_rect.bottom - y0) / dy
            x = x0 + t * dx
            if t > 0 and screen_rect.left <= x <= screen_rect.right:
                t_candidates.append(t)

        if not t_candidates:
            # No intersection in front of the start point; just default to start.
            return start

        # pick the nearest positive intersection
        t_hit = min(t_candidates)
        return (x0 + t_hit * dx, y0 + t_hit * dy)

    def _draw_orbit_to_surface(self, surface: pygame.Surface) -> None:
        if not self.state.julia_orbit:
            return

        orbit = self.state.julia_orbit
        width, height = surface.get_width(), surface.get_height()

        # Draw dots for each point in the orbit
        # for i, point in enumerate(orbit):
        #     screen_coords = self._complex_to_screen_julia(point, width, height)
        #     if screen_coords:
        #         x, y = screen_coords
        # Draw bigger dot for the initial point (Julia constant)
        # if i == 0:
        #     pygame.draw.circle(surface, (255, 0, 0), (x, y), 3)
        # else:
        #     pygame.draw.circle(surface, (255, 255, 255), (x, y), 1)

        @dataclasses.dataclass
        class Rect:
            left: int
            top: int
            right: int
            bottom: int

        # Draw lines connecting consecutive points
        for i in range(len(orbit) - 1):
            start_coords = self._complex_to_screen_julia(orbit[i], width, height)
            end_coords = self._complex_to_screen_julia(orbit[i + 1], width, height)

            # start_coords = self._clip_line_to_surface_boundary(start_coords, end_coords, width, height)
            # end_coords = self._clip_line_to_surface_boundary(start_coords, end_coords, width, height)

            if start_coords and end_coords:
                try:
                    pygame.draw.line(
                        surface, (255, 255, 255), start_coords, end_coords, 1
                    )
                except Exception as e:
                    raise e

    def _complex_to_screen_julia(
        self, z: complex, surface_width: int, surface_height: int
    ):
        width, height = surface_width, surface_height
        aspect_ratio = width / height

        # Calculate the range based on the current zoom level
        height_range = 4.0 / self.state.zoom
        width_range = height_range * aspect_ratio

        # Calculate the bounds of the complex plane view
        re_min = -width_range / 2 + self.state.movement.x
        re_max = width_range / 2 + self.state.movement.x
        im_min = -height_range / 2 + self.state.movement.y
        im_max = height_range / 2 + self.state.movement.y

        # Convert complex coordinates to normalized [0, 1] range
        if re_max == re_min or im_max == im_min:
            return None

        norm_x = (z.real - re_min) / (re_max - re_min)
        norm_y = (z.imag - im_min) / (im_max - im_min)

        # Check if the point is outside the visible range
        if not (0 <= norm_x <= 1 and 0 <= norm_y <= 1):
            return None  # Don't draw points outside the view

        # Convert normalized coordinates to screen pixel coordinates
        screen_x = int(norm_x * width)
        screen_y = int(norm_y * height)

        return screen_x, screen_y

    def _draw_split_view(
        self,
        mandelbrot_surface: pygame.Surface,
        julia_surface: pygame.Surface,
        clock: pygame.time.Clock,
    ):
        self.state.msurface_width = mandelbrot_surface.get_width()
        msurface_width = mandelbrot_surface.get_width()
        msurface_height = mandelbrot_surface.get_height()

        self._draw_mandelbrot_to_surface(mandelbrot_surface, clock)
        self._draw_julia_to_surface(julia_surface, clock)

        if self.state.view_mode == ViewMode.MANDELBROT_SELECTED:
            self._draw_perimeter_to_surface(mandelbrot_surface)
        elif self.state.view_mode == ViewMode.JULIA_SELECTED:
            self._draw_perimeter_to_surface(julia_surface)

        self._draw_cursor_to_surface(
            surface=mandelbrot_surface,
            posx=(msurface_width // 2 + self.state.cursor_pos.x),
            posy=((msurface_height // 2) + self.state.cursor_pos.y),
            cursor_size=min(1, 0.05 * msurface_width),
        )

        return mandelbrot_surface, julia_surface

    def _draw_perimeter_to_surface(self, surface: pygame.Surface) -> None:
        thickness = 2
        width, height = surface.get_size()
        pygame.draw.rect(
            surface,
            (255, 255, 255),
            (0, 0, width, height),
            thickness,
        )

    def _draw_julia_to_surface(
        self, surface: pygame.Surface, clock: pygame.time.Clock
    ) -> None:
        width, height = surface.get_size()
        current_params = (
            self.state.jzoom,
            self.state.jmovement.x,
            self.state.jmovement.y,
            self.state.julia_constant.real,
            self.state.julia_constant.imag,
            self.state.max_iterations,
            width,
            height,
        )
        if self.cached_julia_result is None or self.last_julia_params != current_params:
            aspect_ratio = width / height
            fixed_zoom = self.state.jzoom
            height_range = 4.0 / fixed_zoom
            width_range = height_range * aspect_ratio

            re = np.linspace(
                -width_range / 2 + self.state.jmovement.x,
                width_range / 2 + self.state.jmovement.x,
                width,
            )
            im = np.linspace(
                -height_range / 2 + self.state.jmovement.y,
                height_range / 2 + self.state.jmovement.y,
                height,
            )
            re, im = np.meshgrid(re, im)

            c_real = self.state.julia_constant.real
            c_imag = self.state.julia_constant.imag

            self.cached_julia_result = get_julia_converge_time(
                re, im, c_real, c_imag, self.state.max_iterations
            )
            self.last_julia_params = current_params

        clipped_times = np.clip(
            self.cached_julia_result, 0, len(self.active_palette) - 1
        )
        color_surface = self.active_palette_array[clipped_times]

        surface_array = np.transpose(color_surface, (1, 0, 2))
        pygame.surfarray.blit_array(surface, surface_array)

    def _draw_mandelbrot_to_surface(
        self, surface: pygame.Surface, clock: pygame.time.Clock
    ) -> None:
        width, height = surface.get_size()
        current_params = (
            self.state.zoom,
            self.state.movement.x,
            self.state.movement.y,
            self.state.max_iterations,
            width,
            height,
            self.state.jcursor_pos.x,
            self.state.jcursor_pos.y,
        )

        if self.cached_result is None or self.last_params != current_params:
            self.last_params = current_params
            aspect_ratio = width / height

            height_range = (
                4.0 / self.state.zoom
            )  # Total height range (2.0 * 2 for padding)
            width_range = (
                height_range * aspect_ratio
            )  # Width range adjusted for aspect ratio

            re = np.linspace(
                -width_range / 2 + self.state.movement.x,
                width_range / 2 + self.state.movement.x,
                width,
            )
            im = np.linspace(
                -height_range / 2 + self.state.movement.y,
                height_range / 2 + self.state.movement.y,
                height,
            )
            re, im = np.meshgrid(re, im)
            crit_real = self.state.critical_point.real
            crit_imag = self.state.critical_point.imag
            self.cached_result = get_mandelbrot_converge_time(
                re,
                im,
                crit_real,
                crit_imag,
                self.state.max_iterations,
                self.use_mandelbrot_interior,
            )
            self.last_params = current_params

        clipped_times = np.clip(self.cached_result, 0, len(self.active_palette) - 1)
        color_surface = self.active_palette_array[clipped_times]

        surface_array = np.transpose(color_surface, (1, 0, 2))
        pygame.surfarray.blit_array(surface, surface_array)

    def _draw_fps_to_surface(self, window: pygame.Surface):
        text_color = (255, 255, 255)
        window.blit(
            self.font.render(f"{int(self.clock.get_fps())}", True, text_color), (5, 5)
        )

    def _draw_debug_to_surface(self, window: pygame.Surface):
        text_color = (255, 255, 255)
        init_y = 5
        y_spacing = 10
        text_surfaces = [
            self.font.render(f"X: {self.state.movement.x}", True, text_color),
            self.font.render(f"Y: {self.state.movement.y}", True, text_color),
            self.font.render(f"Iter: {self.state.max_iterations}", True, text_color),
            self.font.render(f"Zoom: {self.state.zoom:e}", True, text_color),
            self.font.render(
                f"Orbit: {len(self.state.julia_orbit or [])}", True, text_color
            ),
        ]
        window.blits(
            [
                (surface, (5, init_y + idx * y_spacing))
                for idx, surface in enumerate(text_surfaces)
            ]
        )

    def _generate_palettes(self, num_colors=256, cycle_length=64):
        base_exponents = (0.5, 2.0, 0.8)
        return [
            self._generate_palette_single(num_colors, cycle_length, permutation)
            for permutation in itertools.permutations(base_exponents, 3)
        ]

    def _generate_palette_single(
        self, num_colors=256, cycle_length=64, base_exponents=(0.5, 2.0, 0.8)
    ):
        colors = []
        for i in range(num_colors):
            if i == 0:
                colors.append((0, 0, 0))  # Black for points in the set
            else:
                r_exp, g_exp, b_exp = base_exponents
                # Create cycling index within the specified cycle length
                cycle_i = i % cycle_length
                # Scale the cycle index to [0,1] range for the color calculation
                t = cycle_i / cycle_length

                r = int(255 * (t**r_exp))
                g = int(255 * (t**g_exp))
                b = int(255 * (t**b_exp))

                pulse = 0.5 + 0.5 * np.sin(2 * np.pi * i / cycle_length)
                r = min(255, int(r * (1.1 + 0.2 * pulse)))
                g = min(255, int(g * (0.7 + 0.2 * pulse)))
                b = min(255, int(b * (1.0 + 0.3 * pulse)))

                colors.append((r, g, b))
        return colors


@jit(nopython=True, fastmath=True, cache=True)
def _is_in_mandelbrot_interior(c_real, c_imag):
    x_minus = c_real - 0.25
    y2 = c_imag * c_imag
    q = x_minus * x_minus + y2

    if q * (q + x_minus) <= 0.25 * y2:
        return True

    if (c_real + 1.0) * (c_real + 1.0) + y2 <= 0.0625:
        return True

    return False


@jit(nopython=True, parallel=True, fastmath=True, cache=True)
def get_mandelbrot_converge_time(
    re, im, critical_real, critical_imag, max_iter, use_interior_check
):
    height, width = re.shape
    result = np.zeros((height, width), dtype=np.int32)

    for i in prange(height):
        for j in range(width):
            c_real = re[i, j]
            c_imag = im[i, j]
            z_real = critical_real
            z_imag = critical_imag
            if use_interior_check and _is_in_mandelbrot_interior(c_real, c_imag):
                continue
            for k in range(max_iter):
                z_real2 = z_real * z_real
                z_imag2 = z_imag * z_imag

                if z_real2 + z_imag2 > 4.0:
                    result[i, j] = k
                    break

                # i.e. with expanding (a + bi)^2 to a^2 + 2abi + b^2
                z_imag = 2.0 * z_real * z_imag + c_imag
                z_real = z_real2 - z_imag2 + c_real

    return result


@jit(nopython=True, parallel=True, fastmath=True, cache=True)
def get_mandelbrot_converge_time_into(
    re, im, critical_real, critical_imag, max_iter, use_interior_check, result
):
    height, width = re.shape

    for i in prange(height):
        for j in range(width):
            c_real = re[i, j]
            c_imag = im[i, j]
            z_real = critical_real
            z_imag = critical_imag
            if use_interior_check and _is_in_mandelbrot_interior(c_real, c_imag):
                result[i, j] = 0
                continue
            for k in range(max_iter):
                z_real2 = z_real * z_real
                z_imag2 = z_imag * z_imag

                if z_real2 + z_imag2 > 4.0:
                    result[i, j] = k
                    break

                z_imag = 2.0 * z_real * z_imag + c_imag
                z_real = z_real2 - z_imag2 + c_real
            else:
                result[i, j] = 0

    return result


@jit(nopython=True, parallel=True, fastmath=True, cache=True)
def get_julia_converge_time(re, im, c_real, c_imag, max_iter):
    height, width = re.shape
    result = np.zeros((height, width), dtype=np.int32)
    c = complex(c_real, c_imag)

    for i in prange(height):
        for j in range(width):
            z = complex(re[i, j], im[i, j])
            for k in range(max_iter):
                z = (z * z) + c
                if abs(z) > 2:
                    result[i, j] = k
                    break

    return result


def main() -> None:
    import pygame

    from heart.device.local import LocalScreen
    from heart.runtime.container import build_runtime_container
    from heart.runtime.render.pipeline import RendererVariant
    from heart.utilities.env import Configuration

    profiling = os.environ.get("PROFILING", "False").lower() == "true"
    check_frames = int(os.environ.get("CHECK_FRAMES", "100"))

    # Initialize pygame
    pygame.init()

    # Set up the display
    width, height = 512, 256
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Mandelbrot Explorer")

    # Create the mandelbrot renderer
    mandelbrot = MandelbrotMode()

    # Main game loop
    running = True
    clock = pygame.time.Clock()
    if profiling:
        profiler = cProfile.Profile()
        profile_filename = "mandelbrot_profile.prof"
        profiler.enable()

    frame_count = 0

    render_variant = RendererVariant.parse(Configuration.render_variant())
    orientation = Rectangle.with_layout(1, 1)
    device = LocalScreen(width=width, height=height, orientation=orientation)
    container = build_runtime_container(
        device=device,
        render_variant=render_variant,
    )
    manager = container.resolve(PeripheralManager)
    manager.detect()
    manager.start()
    try:
        while running:
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            # Fill the screen with black
            screen.fill((0, 0, 0))

            # Process and render
            mandelbrot._internal_process(screen, clock, manager, orientation)

            # Update the display
            pygame.display.flip()
            frame_count += 1

            if profiling and (frame_count >= check_frames):
                profiler.disable()
                profiler.dump_stats(profile_filename)
                break

            clock.tick(60)
    finally:
        if profiling:
            # === Profiling Teardown and Analysis ===
            profiler.disable()  # Stop profiling
            logger.info("Profiling finished after %s frames.", frame_count)

            # --- Option 1: Print stats to console ---
            s = io.StringIO()
            # Sort by cumulative time spent in function and its callees
            ps = pstats.Stats(profiler, stream=s).sort_stats("cumulative")
            ps.print_stats(30)  # Print top 30 lines
            logger.info("--- Profiling Stats (Sorted by Cumulative Time) ---")
            logger.info("%s", s.getvalue())

            # You might also want to sort by 'tottime' (total time spent ONLY in the function itself)
            s = io.StringIO()
            ps = pstats.Stats(profiler, stream=s).sort_stats("tottime")
            ps.print_stats(30)  # Print top 30 lines
            logger.info("--- Profiling Stats (Sorted by Total Time) ---")
            logger.info("%s", s.getvalue())

            # --- Option 2: Save stats to a file for later analysis ---
            profiler.dump_stats(profile_filename)
            logger.info("Profiling data saved to %s", profile_filename)
            logger.info(
                "You can analyze this file later, e.g., using 'snakeviz %s'",
                profile_filename,
            )
        pygame.quit()


if __name__ == "__main__":
    main()
