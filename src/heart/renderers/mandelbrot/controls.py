import cmath
import math

import numpy as np

from heart.renderers.mandelbrot.state import AppState, ViewMode

DEFAULT_PAN_ZOOM: float | None = None
DEFAULT_CURSOR_DELTA = 0
DEFAULT_CURSOR_MODE = "julia"
DEFAULT_PALETTE_FORWARD = True
DEFAULT_SHOW_FPS: bool | None = None
DEFAULT_EXPLICIT_MODE: str | None = None
DEFAULT_MOVE_MULTIPLIER = 1.0


class SceneControls:
    def __init__(self, state: AppState):
        self.state = state
        self.reset_requested = False
        self.quit_requested = False

    @staticmethod
    def clamp(value: float, lo: float, hi: float):
        return max(lo, min(value, hi))

    def disable_auto(self):
        self.state.mode = "free"

    def get_pan_amount(self, zoom: float | None = DEFAULT_PAN_ZOOM):
        pan_scaling = 0.05
        return pan_scaling / zoom

    def get_zoom_amount(self):
        zoom_scaling = 1.1
        return self.state.zoom * zoom_scaling

    def _reset_all(self):
        # self._reset_julia()
        # self._reset_mandelbrot()
        self.state.reset()

    def update_cursor_pos(
        self,
        delta_x: int = DEFAULT_CURSOR_DELTA,
        delta_y: int = DEFAULT_CURSOR_DELTA,
        cursor: str = DEFAULT_CURSOR_MODE,
    ):
        padding = 3
        y_lo_bound = -(self.state.msurface_height // 2) + padding  # - 2
        y_hi_bound = (self.state.msurface_height // 2) - padding  # - padding + 1
        x_lo_bound = -(self.state.msurface_width // 2) + padding  # + padding + 0.5
        x_hi_bound = (self.state.msurface_width // 2) - padding  # - padding - 1

        if cursor == "julia":
            virtual_cursor = self.state.cursor_pos
        else:
            virtual_cursor = self.state.jcursor_pos

        target_x = virtual_cursor.x + delta_x
        target_y = virtual_cursor.y + delta_y

        # i.e. clamp cursor to the boundary
        self.state.cursor_pos.x = min(max(target_x, x_lo_bound), x_hi_bound)
        self.state.cursor_pos.y = min(max(target_y, y_lo_bound), y_hi_bound)

        # start panning if cursor is "pushing" the boundary
        if target_x < x_lo_bound:
            self._move_left("panning")
        elif target_x > x_hi_bound:
            self._move_right("panning")

        if target_y < y_lo_bound:
            self._move_up("panning")
        elif target_y > y_hi_bound:
            self._move_down("panning")

    def cycle_palette(self, forward: bool = DEFAULT_PALETTE_FORWARD):
        step = 1 if forward else -1
        self.state.palette_index = (
            self.state.palette_index + step
        ) % self.state.num_palettes

    def _reset_julia(self):
        self.state.jmovement.x = 0
        self.state.jmovement.y = 0
        self.state.jzoom = 2.0

    def _reset_mandelbrot(self):
        self.state.movement.x = self.state._init_x
        self.state.movement.y = self.state._init_y
        self.state.zoom = 1.0

    def _toggle_selected_surface(self):
        self.state.selected_surface = (
            "mandelbrot" if self.state.selected_surface == "julia" else "julia"
        )
        self._reset_julia()

    def _increment_view_mode(self):
        self.state.set_mode_free()
        if self.state.view_mode == ViewMode.MANDELBROT:
            # self.state.
            self._reset_julia()
            self.state.cursor_pos.x = 0
            self.state.cursor_pos.y = 0
            self._update_julia_constant()
        self.state.view_mode = min(self.state.view_mode + 1, len(ViewMode) - 1)

    def _decrement_view_mode(self):
        self.state.set_mode_free()
        self.state.view_mode = max(self.state.view_mode - 1, 0)

    @property
    def movement_mode(self):
        return (
            "cursor"
            if self.state.view_mode == ViewMode.MANDELBROT_SELECTED
            else "panning"
        )

    # Common action methods
    def _toggle_julia_mode(self):
        self.state.julia_mode = not self.state.julia_mode
        self.state.movement_mode = "cursor" if self.state.julia_mode else "panning"
        self.state.show_left_cursor = self.state.julia_mode

    def _toggle_fps(self, show: bool | None = DEFAULT_SHOW_FPS):
        if show is None:
            self.state.show_fps = not self.state.show_fps
        else:
            self.state.show_fps = show

    def _toggle_debug(self, show: bool = None):
        if show is None:
            self.state.show_debug = not self.state.show_debug
        else:
            self.state.show_debug = show

    def _update_critical_point(self):
        self.state.critical_point = complex(
            *self.screen_to_complex(self.state.jcursor_pos.x, self.state.jcursor_pos.y)
        )

    def _update_julia_constant(self):
        self.state.julia_constant = complex(
            *self.screen_to_complex(self.state.cursor_pos.x, self.state.cursor_pos.y)
        )
        if self.state.julia_constant:
            self._calculate_julia_orbit()

    def _calculate_julia_orbit(self):
        point = self.state.julia_constant
        orbit = [point]
        for i in range(self.state.max_iterations):
            try:
                point = (point * point) + self.state.julia_constant
                orbit.append(point)
                # if abs(point) > 2:
                #     break
            except Exception:
                # todo: sometimes orbit calc fails bc overflow
                pass

        self.state.julia_orbit = orbit

    def _calculate_mandelbrot_orbit_music(self, max_iterations=100, scale=None):
        """Calculate musical properties from a Mandelbrot orbit at point c."""
        c = self.state.julia_constant
        if scale is None:
            # C minor pentatonic scale frequencies (Hz)
            scale = [261.63, 311.13, 349.23, 392.00, 466.16]

        z = 0
        orbit = [z]
        seen_points = {0}

        for i in range(max_iterations):
            z = z * z + c

            # Round to handle floating point precision issues
            z_rounded = complex(round(z.real, 10), round(z.imag, 10))

            # Check for cycle
            if z_rounded in seen_points:
                # Found a cycle
                cycle_start = list(seen_points).index(z_rounded)
                cycle_length = len(orbit) - cycle_start

                # Musical mapping
                notes = []
                cycle = orbit[cycle_start:]

                for point in cycle:
                    # Map magnitude to note index
                    mag = abs(point)
                    if mag > 2:  # Escape orbit
                        note_index = len(scale) - 1  # Highest note
                    else:
                        # Normalize magnitude between 0 and 1, then scale to notes
                        normalized_mag = min(mag / 2, 1.0)
                        note_index = int(normalized_mag * (len(scale) - 1))

                    # Map angle to duration or velocity
                    angle = (cmath.phase(point) + math.pi) / (
                        2 * math.pi
                    )  # Normalize to 0-1
                    duration = 0.1 + angle * 0.4  # Duration between 0.1 and 0.5 seconds

                    notes.append(
                        {
                            "frequency": scale[note_index],
                            "duration": duration,
                            "magnitude": mag,
                            "angle": angle,
                        }
                    )

                return {
                    "is_bounded": True,
                    "cycle_length": cycle_length,
                    "orbit_length": len(orbit),
                    "notes": notes,
                    "cycle_start": cycle_start,
                }

            orbit.append(z)
            seen_points.add(z_rounded)

            if abs(z) > 2:
                # Unbounded orbit - escaped
                # Could map the escape speed to something musical
                escape_speed = i / max_iterations
                return {
                    "is_bounded": False,
                    "escape_iteration": i,
                    "orbit_length": len(orbit),
                    "escape_speed": escape_speed,
                }

        # Reached max iterations without finding cycle or escaping
        return {
            "is_bounded": True,  # Assumed bounded
            "orbit_length": len(orbit),
            "notes": None,  # No clear cycle detected
        }

    def _move(
        self,
        x: int,
        y: int,
        explicit_mode: str | None = DEFAULT_EXPLICIT_MODE,
        multiplier: float = DEFAULT_MOVE_MULTIPLIER,
    ):
        cursor_mode = explicit_mode or "cursor"
        self.disable_auto()
        x = x * multiplier
        y = y * multiplier
        match self.state.view_mode:
            case ViewMode.MANDELBROT:
                # self.state.movement.x += x * self.get_pan_amount(self.state.zoom)
                self.state.movement.x = self.clamp(
                    self.state.movement.x + x * self.get_pan_amount(self.state.zoom),
                    -2.0,
                    2.0,
                )
                # self.state.movement.y += y * self.get_pan_amount(self.state.zoom)
                self.state.movement.y = self.clamp(
                    self.state.movement.y + y * self.get_pan_amount(self.state.zoom),
                    -2.0,
                    2.0,
                )
            case ViewMode.MANDELBROT_SELECTED:
                self._reset_julia()
                match cursor_mode:
                    case "cursor":
                        self.update_cursor_pos(delta_x=x, delta_y=y)
                    case _:
                        self.state.movement.x = self.clamp(
                            self.state.movement.x
                            + x * self.get_pan_amount(self.state.zoom),
                            -2.0,
                            2.0,
                        )
                        self.state.movement.y = self.clamp(
                            self.state.movement.y
                            + y * self.get_pan_amount(self.state.zoom),
                            -2.0,
                            2.0,
                        )
                self._update_julia_constant()
            case ViewMode.JULIA_SELECTED | ViewMode.JULIA:
                # self.state.jmovement.x += x * self.get_pan_amount(self.state.jzoom)
                self.state.jmovement.x = self.clamp(
                    self.state.jmovement.x + x * self.get_pan_amount(self.state.jzoom),
                    -2.0,
                    2.0,
                )
                # self.state.jmovement.y += y * self.get_pan_amount(self.state.jzoom)
                self.state.jmovement.y = self.clamp(
                    self.state.jmovement.y + y * self.get_pan_amount(self.state.jzoom),
                    -2.0,
                    2.0,
                )

        # if self.state.view_mode == ViewMode.MANDELBROT_SELECTED:
        #     if mode == "cursor":
        #         self.update_cursor_pos(delta_x=x, delta_y=y, cursor=cursor)
        #         self._update_julia_constant()
        #     else:
        #         self.state.movement.x += x * self.get_pan_amount(self.state.zoom)
        #         self.state.movement.y += y * self.get_pan_amount(self.state.zoom)
        #
        # elif self.state.selected_surface == "julia":
        #     self.state.jmovement.x += x * self.get_pan_amount(self.state.jzoom)
        #     self.state.jmovement.y += y * self.get_pan_amount(self.state.jzoom)

    # Movement handlers
    def _move_up(self, explicit_mode: str | None = DEFAULT_EXPLICIT_MODE):
        self._move(0, -1, explicit_mode=explicit_mode)
        # mode = explicit_mode or self.state.movement_mode
        # if mode == "cursor":
        #     self.update_cursor_pos(delta_y=-1)
        #     self._update_julia_constant()
        # else:
        #     self.state.movement.y -= self.get_pan_amount()

    def _move_down(self, explicit_mode: str | None = DEFAULT_EXPLICIT_MODE):
        self._move(0, 1, explicit_mode=explicit_mode)
        # mode = explicit_mode or self.state.movement_mode
        # if mode == "cursor":
        #     self.update_cursor_pos(delta_y=1)
        #     self._update_julia_constant()
        # else:
        #     self.state.movement.y += self.get_pan_amount()

    def _move_left(self, explicit_mode: str | None = DEFAULT_EXPLICIT_MODE):
        self._move(-1, 0, explicit_mode=explicit_mode)
        # mode = explicit_mode or self.state.movement_mode
        # if mode == "cursor":
        #     self.update_cursor_pos(delta_x=-1)
        #     self._update_julia_constant()
        # else:
        #     if self.state.selected_surface == "mandelbrot":
        #         self.state.movement.x -= self.get_pan_amount()
        #     elif self.state.selected_surface == "julia":
        #         self.state.jmovement.x -= self.get_pan_amount()

    def _move_right(self, explicit_mode: str | None = DEFAULT_EXPLICIT_MODE):
        self._move(1, 0, explicit_mode=explicit_mode)
        # mode = explicit_mode or self.state.movement_mode
        # if mode == "cursor":
        #     self.update_cursor_pos(delta_x=1)
        #     self._update_julia_constant()
        # else:
        #     self.state.movement.x += self.get_pan_amount()

    def _zoom_in(self):
        self.disable_auto()
        match self.state.view_mode:
            case ViewMode.MANDELBROT:
                self.state.zoom = min(1e14, self.state.zoom * 1.05)
            case ViewMode.JULIA | ViewMode.JULIA_SELECTED:
                self.state.jzoom = min(1e14, self.state.jzoom * 1.05)
            case ViewMode.MANDELBROT_SELECTED:
                cursor_re, cursor_im = self.screen_to_complex(
                    self.state.cursor_pos.x, self.state.cursor_pos.y
                )

                # Apply zoom
                old_zoom = self.state.zoom
                self.state.zoom = min(1e14, self.state.zoom * 1.05)

                # Calculate how the view center needs to shift to keep cursor point fixed
                zoom_factor_change = self.state.zoom / old_zoom

                # Adjust movement to keep the cursor point fixed during zoom
                self.state.movement.x = (
                    cursor_re - (cursor_re - self.state.movement.x) / zoom_factor_change
                )
                self.state.movement.y = (
                    cursor_im - (cursor_im - self.state.movement.y) / zoom_factor_change
                )

        # if self.state.julia_mode:
        #     if self.state.selected_surface == "mandelbrot":
        #         # Get the complex coordinates of the cursor before zooming
        #         cursor_re, cursor_im = self.screen_to_complex(
        #             self.state.cursor_pos.x,
        #             self.state.cursor_pos.y
        #         )
        #
        #         # Apply zoom
        #         old_zoom = self.state.zoom
        #         self.state.zoom = min(1e14, self.state.zoom * 1.1)
        #
        #         # Calculate how the view center needs to shift to keep cursor point fixed
        #         zoom_factor_change = self.state.zoom / old_zoom
        #
        #         # Adjust movement to keep the cursor point fixed during zoom
        #         self.state.movement.x = cursor_re - (cursor_re - self.state.movement.x) / zoom_factor_change
        #         self.state.movement.y = cursor_im - (cursor_im - self.state.movement.y) / zoom_factor_change
        #     elif self.state.selected_surface == "julia":
        #         # there is no cursor now
        #         self.state.jzoom = min(1e14, self.state.jzoom * 1.1)
        # else:
        #     # Original behavior for non-Julia mode
        #     self.state.zoom = min(1e14, self.state.zoom * 1.1)

    def _zoom_out(self):
        self.disable_auto()
        match self.state.view_mode:
            case ViewMode.MANDELBROT:
                self.state.zoom = max(self.state.zoom / 1.05, 3e-1)
            case ViewMode.JULIA | ViewMode.JULIA_SELECTED:
                self.state.jzoom = max(self.state.jzoom / 1.05, 3e-1)
            case ViewMode.MANDELBROT_SELECTED:
                # Same principle as zoom in, but with opposite zoom direction
                cursor_re, cursor_im = self.screen_to_complex(
                    self.state.cursor_pos.x, self.state.cursor_pos.y
                )

                old_zoom = self.state.zoom
                self.state.zoom = max(self.state.zoom / 1.05, 3e-1)

                zoom_factor_change = self.state.zoom / old_zoom

                # Adjust movement to keep the cursor point fixed during zoom
                self.state.movement.x = (
                    cursor_re - (cursor_re - self.state.movement.x) / zoom_factor_change
                )
                self.state.movement.y = (
                    cursor_im - (cursor_im - self.state.movement.y) / zoom_factor_change
                )

    def _increase_max_iterations(self):
        self.state.max_iterations += 1

    def _decrease_max_iterations(self):
        self.state.max_iterations -= 1

    # System handlers
    def _request_reset(self):
        self.reset_requested = True
        self.state.mode = "auto"

    def _request_quit(self):
        self.quit_requested = True

    def _enable_auto(self):
        self._request_reset()
        self.state.mode = "auto"

    def _toggle_left_cursor(self):
        if self.state.julia_mode:
            self.state.movement_mode = (
                "cursor" if self.state.movement_mode != "cursor" else "panning"
            )
            # reset cursor if entering cursor mode
            if self.state.movement_mode == "cursor":
                self.state.cursor_pos.x = 0
                self.state.cursor_pos.y = 0
                self._update_julia_constant()
            self.state.show_left_cursor = self.state.movement_mode == "cursor"

    def _toggle_right_cursor(self):
        # self.state.show_right_cursor = not self.state.show_right_cursor
        pass

    def screen_to_complex(self, screen_x, screen_y):
        width, height = self.state.msurface_width // 2, self.state.msurface_height // 2
        aspect_ratio = width / height

        height_range = 4.0 / self.state.zoom  # Total height range
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

        # Normalize screen coordinates
        normalized_x = screen_x / width
        normalized_y = screen_y / height

        # Get corresponding complex values
        re_val = self.get_value_from_normalized_position(re, normalized_x)
        im_val = self.get_value_from_normalized_position(im, normalized_y)

        return re_val, im_val

    def get_value_from_normalized_position(self, array, normalized_position):
        # Ensure position is within bounds
        normalized_position = np.clip(normalized_position, -1, 1)

        # Map from [-1, 1] to [0, len(array)-1]
        index_float = ((normalized_position + 1) / 2) * (len(array) - 1)

        # Get the integer index
        index = int(index_float)

        return array[index]

    def process_events(self):
        """Override this method in derived classes to handle specific input devices."""
        pass
