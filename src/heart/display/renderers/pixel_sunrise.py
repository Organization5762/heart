"""OpenGL renderer that pixelates a ray-traced sun across the ground plane."""

from __future__ import annotations

import importlib.util
import time
from typing import Any, Optional

import numpy as np
import pygame
from OpenGL.GL import (GL_ARRAY_BUFFER, GL_COLOR_BUFFER_BIT, GL_COMPILE_STATUS,
                       GL_FALSE, GL_FLOAT, GL_FRAGMENT_SHADER, GL_LINK_STATUS,
                       GL_RGB, GL_STATIC_DRAW, GL_TRIANGLE_STRIP, GL_TRUE,
                       GL_UNSIGNED_BYTE, GL_VERTEX_SHADER, glAttachShader,
                       glBindAttribLocation, glBindBuffer, glBufferData,
                       glClear, glClearColor, glCompileShader, glCreateProgram,
                       glCreateShader, glDeleteProgram, glDeleteShader,
                       glDisableVertexAttribArray, glDrawArrays,
                       glEnableVertexAttribArray, glGenBuffers,
                       glGetProgramInfoLog, glGetProgramiv, glGetShaderInfoLog,
                       glGetShaderiv, glGetUniformLocation, glLinkProgram,
                       glReadPixels, glShaderSource, glUniform1f, glUniform2f,
                       glUseProgram, glVertexAttribPointer, glViewport)

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.peripheral.core.manager import PeripheralManager

_SDL2Window: Any | None
_SDL2_WINDOW_SPEC = importlib.util.find_spec("pygame._sdl2.video")
if _SDL2_WINDOW_SPEC is not None:
    from pygame._sdl2 import video as _sdl2_video  # type: ignore[import]

    _SDL2Window = _sdl2_video.Window
else:
    _SDL2Window = None


VERT_SHADER = """
#version 120

attribute vec2 a_position;
varying vec2 v_uv;

void main() {
    v_uv = a_position * 0.5 + 0.5;
    gl_Position = vec4(a_position, 0.0, 1.0);
}
"""


FRAG_SHADER = """
#version 120

uniform float u_time;
uniform vec2 u_resolution;

varying vec2 v_uv;

const float PI = 3.14159265358979;

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

vec2 pixel_snap(vec2 frag_coord, vec2 resolution, float target_rows) {
    float step_y = max(1.0, floor(resolution.y / target_rows));
    vec2 snapped = floor(frag_coord / step_y) * step_y + step_y * 0.5;
    return snapped / resolution;
}

bool intersect_sphere(
    vec3 ray_origin,
    vec3 ray_direction,
    vec3 center,
    float radius,
    out float hit_t
) {
    vec3 oc = ray_origin - center;
    float b = dot(oc, ray_direction);
    float c = dot(oc, oc) - radius * radius;
    float discriminant = b * b - c;
    if (discriminant < 0.0) {
        return false;
    }
    float s = sqrt(discriminant);
    float t0 = -b - s;
    float t1 = -b + s;
    float t = t0;
    if (t < 0.0) {
        t = t1;
    }
    if (t < 0.0) {
        return false;
    }
    hit_t = t;
    return true;
}

float intersect_ground(vec3 ray_origin, vec3 ray_direction) {
    if (ray_direction.y >= -0.0001) {
        return -1.0;
    }
    float t = -ray_origin.y / ray_direction.y;
    return t > 0.0 ? t : -1.0;
}

float intersect_column(vec3 ray_origin, vec3 ray_direction, float radius, float height) {
    vec2 origin_xz = ray_origin.xz;
    vec2 direction_xz = ray_direction.xz;
    float a = dot(direction_xz, direction_xz);
    if (abs(a) < 1e-5) {
        return -1.0;
    }
    float b = 2.0 * dot(origin_xz, direction_xz);
    float c = dot(origin_xz, origin_xz) - radius * radius;
    float discriminant = b * b - 4.0 * a * c;
    if (discriminant < 0.0) {
        return -1.0;
    }
    float s = sqrt(discriminant);
    float t0 = (-b - s) / (2.0 * a);
    float t1 = (-b + s) / (2.0 * a);
    float t = 1e6;
    if (t0 > 0.0) {
        t = t0;
    }
    if (t1 > 0.0) {
        t = min(t, t1);
    }
    if (t == 1e6) {
        return -1.0;
    }
    float y_hit = ray_origin.y + ray_direction.y * t;
    if (y_hit < 0.0 || y_hit > height) {
        return -1.0;
    }
    return t;
}

bool column_shadow(
    vec3 point,
    vec3 to_light,
    vec3 sun_position,
    float radius,
    float height
) {
    float distance = length(sun_position - point);
    vec3 origin = point + to_light * 0.02;
    float t = intersect_column(origin, to_light, radius, height);
    return t > 0.0 && t < distance;
}

vec3 sky_color(vec3 ray_direction, vec3 sun_direction, float sun_height) {
    float horizon = clamp(ray_direction.y * 0.5 + 0.5, 0.0, 1.0);
    vec3 night_top = vec3(0.02, 0.04, 0.1);
    vec3 day_top = vec3(0.35, 0.5, 0.82);
    vec3 dusk = vec3(0.75, 0.4, 0.35);
    vec3 top = mix(night_top, day_top, sun_height);
    vec3 horizon_color = mix(dusk, vec3(0.2, 0.3, 0.45), sun_height);
    vec3 base = mix(horizon_color, top, horizon);
    float halo = pow(max(dot(ray_direction, sun_direction), 0.0), 64.0);
    base += vec3(1.0, 0.8, 0.5) * halo * (0.3 + 0.7 * sun_height);
    float dusk_tint = smoothstep(0.0, 0.2, 1.0 - sun_height);
    base = mix(base, vec3(0.12, 0.06, 0.12), dusk_tint * (1.0 - horizon));
    return base;
}

void main() {
    vec2 frag_coord = gl_FragCoord.xy;
    float target_rows = 96.0;
    vec2 snapped_uv = pixel_snap(frag_coord, u_resolution, target_rows);
    vec2 ndc = snapped_uv * 2.0 - 1.0;
    ndc.x *= u_resolution.x / u_resolution.y;

    vec3 camera_pos = vec3(0.0, 1.2, 4.5);
    vec3 target = vec3(0.0, 1.0, 0.0);
    vec3 up = vec3(0.0, 1.0, 0.0);
    vec3 forward = normalize(target - camera_pos);
    vec3 right = normalize(cross(forward, up));
    vec3 camera_up = normalize(cross(right, forward));
    float focal = 1.4;
    vec3 ray_dir = normalize(forward * focal + ndc.x * right + ndc.y * camera_up);

    float cycle = u_time * 0.02;
    float day = fract(cycle);
    float azimuth = mix(-1.3, 1.3, day);
    float altitude = sin(day * PI);
    vec3 sun_pos = vec3(azimuth * 5.0, 0.25 + 4.0 * altitude, -6.0);
    float sun_radius = 0.65;
    vec3 sun_dir = normalize(sun_pos - camera_pos);
    float sun_height = clamp((sun_pos.y - 0.1) / 4.2, 0.0, 1.0);

    vec3 color = sky_color(ray_dir, sun_dir, sun_height);
    float nearest = 1e6;

    float t_sun;
    if (intersect_sphere(camera_pos, ray_dir, sun_pos, sun_radius, t_sun)) {
        nearest = t_sun;
        vec3 hit = camera_pos + ray_dir * t_sun;
        vec3 normal = normalize(hit - sun_pos);
        float glow = pow(max(dot(normal, -ray_dir), 0.0), 3.0);
        float rim = pow(1.0 - max(dot(normal, sun_dir), 0.0), 2.0);
        vec3 sun_color = vec3(1.0, 0.84, 0.46) * (1.5 + glow);
        sun_color += vec3(1.0, 0.6, 0.3) * rim;
        color = clamp(sun_color, 0.0, 2.0);
    }

    float column_radius = 0.22;
    float column_height = 1.4;
    float t_column = intersect_column(camera_pos, ray_dir, column_radius, column_height);
    if (t_column > 0.0 && t_column < nearest) {
        nearest = t_column;
        vec3 hit = camera_pos + ray_dir * t_column;
        vec3 normal = normalize(vec3(hit.x, 0.0, hit.z));
        vec3 light_dir = normalize(sun_pos - hit);
        float diffuse = max(dot(normal, light_dir), 0.0);
        float ambient = 0.25 + 0.45 * sun_height;
        vec3 column_color = vec3(0.35, 0.31, 0.28) * (ambient + diffuse);
        float specular = pow(max(dot(reflect(-light_dir, normal), -ray_dir), 0.0), 8.0);
        column_color += vec3(0.6, 0.45, 0.35) * specular * (0.3 + 0.7 * sun_height);
        color = column_color;
    }

    float t_ground = intersect_ground(camera_pos, ray_dir);
    if (t_ground > 0.0 && t_ground < nearest) {
        nearest = t_ground;
        vec3 hit = camera_pos + ray_dir * t_ground;
        vec3 light_dir = normalize(sun_pos - hit);
        float visible = step(0.1, sun_pos.y);
        float occluded = column_shadow(hit, light_dir, sun_pos, column_radius, column_height) ? 0.0 : 1.0;
        float lambert = max(dot(vec3(0.0, 1.0, 0.0), light_dir), 0.0) * occluded * visible;
        float ambient = mix(0.15, 0.45, sun_height);
        vec2 tile = floor(hit.xz * 0.6);
        float checker = mod(tile.x + tile.y, 2.0);
        vec3 base = mix(vec3(0.24, 0.33, 0.2), vec3(0.32, 0.36, 0.16), checker);
        base += 0.04 * sin(hit.x * 3.5) * vec3(0.3, 0.18, 0.1);
        vec3 ground_color = base * (ambient + lambert);
        float warm_edge = smoothstep(-0.3, 0.2, hit.z);
        ground_color += vec3(0.6, 0.38, 0.2) * (1.0 - sun_height) * warm_edge * 0.25;
        color = ground_color;
    }

    float palette_levels = 6.0;
    float step_y = max(1.0, floor(u_resolution.y / target_rows));
    vec2 cell = floor(frag_coord / step_y);
    float dither = hash(cell);
    vec3 quantized = floor(clamp(color, 0.0, 1.0) * palette_levels + dither * 0.75) / palette_levels;

    gl_FragColor = vec4(quantized, 1.0);
}
"""


class PixelSunriseRenderer(BaseRenderer):
    """Render a sun arc and ground with a pixel-art quantizing shader."""

    def __init__(self) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.OPENGL
        self.warmup = False

        self._program: Optional[int] = None
        self._vertex_buffer: Optional[int] = None
        self._quad_vertices = np.array(
            [-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0], dtype=np.float32
        )

        self._start_time: float | None = None
        self._uniform_time: Optional[int] = None
        self._uniform_resolution: Optional[int] = None
        self._pixel_buffer: Optional[np.ndarray] = None

    @staticmethod
    def _get_drawable_size(window: pygame.Surface) -> tuple[int, int]:
        if _SDL2Window is None:
            return window.get_size()

        try:
            sdl_window = _SDL2Window.from_display_module()
        except Exception:
            return window.get_size()

        if sdl_window is None:
            return window.get_size()

        drawable_size = getattr(sdl_window, "drawable_size", None)
        if not drawable_size:
            return window.get_size()

        drawable_width, drawable_height = drawable_size
        return int(drawable_width), int(drawable_height)

    def _ensure_pixel_buffer(self, size: tuple[int, int]) -> None:
        width, height = size
        if (
            self._pixel_buffer is None
            or self._pixel_buffer.shape[0] != height
            or self._pixel_buffer.shape[1] != width
        ):
            self._pixel_buffer = np.zeros((height, width, 3), dtype=np.uint8)

    def _compile_shader(self, source: str, shader_type: int) -> int:
        shader = glCreateShader(shader_type)
        glShaderSource(shader, source)
        glCompileShader(shader)
        status = glGetShaderiv(shader, GL_COMPILE_STATUS)
        if status != GL_TRUE:
            log = glGetShaderInfoLog(shader)
            glDeleteShader(shader)
            raise RuntimeError(f"Shader compilation failed: {log!r}")
        return shader

    def _create_program(self) -> int:
        vertex_shader = self._compile_shader(VERT_SHADER, GL_VERTEX_SHADER)
        fragment_shader = self._compile_shader(FRAG_SHADER, GL_FRAGMENT_SHADER)

        program = glCreateProgram()
        glAttachShader(program, vertex_shader)
        glAttachShader(program, fragment_shader)
        glBindAttribLocation(program, 0, "a_position")
        glLinkProgram(program)

        status = glGetProgramiv(program, GL_LINK_STATUS)
        if status != GL_TRUE:
            log = glGetProgramInfoLog(program)
            glDeleteShader(vertex_shader)
            glDeleteShader(fragment_shader)
            glDeleteProgram(program)
            raise RuntimeError(f"Program link failed: {log!r}")

        glDeleteShader(vertex_shader)
        glDeleteShader(fragment_shader)
        return program

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if self._program is None:
            self._program = self._create_program()
            self._vertex_buffer = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self._vertex_buffer)
            glBufferData(
                GL_ARRAY_BUFFER,
                self._quad_vertices.nbytes,
                self._quad_vertices,
                GL_STATIC_DRAW,
            )
            glBindBuffer(GL_ARRAY_BUFFER, 0)

            glUseProgram(self._program)
            self._uniform_time = glGetUniformLocation(self._program, "u_time")
            self._uniform_resolution = glGetUniformLocation(
                self._program, "u_resolution"
            )

        if self._start_time is None:
            self._start_time = time.perf_counter()

        glUseProgram(self._program)
        width, height = self._get_drawable_size(window)
        if self._uniform_resolution is not None:
            glUniform2f(self._uniform_resolution, float(width), float(height))

        super().initialize(window, clock, peripheral_manager, orientation)

    def process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if self._program is None:
            self.initialize(window, clock, peripheral_manager, orientation)
            if self._program is None:
                return

        surface_width, surface_height = window.get_size()
        if surface_width == 0 or surface_height == 0:
            return

        frame_width, frame_height = self._get_drawable_size(window)
        if frame_width == 0 or frame_height == 0:
            return

        self._ensure_pixel_buffer((frame_width, frame_height))

        start_time = self._start_time or time.perf_counter()
        elapsed = time.perf_counter() - start_time

        glUseProgram(self._program)
        if self._uniform_time is not None:
            glUniform1f(self._uniform_time, float(elapsed))
        if self._uniform_resolution is not None:
            glUniform2f(
                self._uniform_resolution, float(frame_width), float(frame_height)
            )

        glViewport(0, 0, frame_width, frame_height)
        glClearColor(0.05, 0.07, 0.12, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)

        glBindBuffer(GL_ARRAY_BUFFER, self._vertex_buffer or 0)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, None)
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
        glDisableVertexAttribArray(0)

        glReadPixels(
            0,
            0,
            frame_width,
            frame_height,
            GL_RGB,
            GL_UNSIGNED_BYTE,
            self._pixel_buffer,
        )

        if self._pixel_buffer is None:
            return

        flipped = np.flipud(self._pixel_buffer)
        frame_array = np.transpose(flipped, (1, 0, 2))

        if (frame_width, frame_height) == (surface_width, surface_height):
            pygame.surfarray.blit_array(window, frame_array)
        else:
            frame_surface = pygame.surfarray.make_surface(frame_array)
            scaled_surface = pygame.transform.smoothscale(
                frame_surface, (surface_width, surface_height)
            )
            window.blit(scaled_surface, (0, 0))

        clock.tick_busy_loop(60)

