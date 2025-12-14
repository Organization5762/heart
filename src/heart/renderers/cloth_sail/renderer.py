"""OpenGL fragment shader cloth simulation for the four-panel display."""

from __future__ import annotations

import importlib.util
import math
from typing import Any, Optional

import numpy as np
import pygame
import reactivex
from OpenGL.GL import (GL_ARRAY_BUFFER, GL_COLOR_BUFFER_BIT, GL_COMPILE_STATUS,
                       GL_CULL_FACE, GL_DEPTH_TEST, GL_FALSE, GL_FLOAT,
                       GL_FRAGMENT_SHADER, GL_LINK_STATUS, GL_PACK_ALIGNMENT,
                       GL_RGB, GL_STATIC_DRAW, GL_TRIANGLE_STRIP,
                       GL_UNSIGNED_BYTE, GL_VERTEX_SHADER, glAttachShader,
                       glBindAttribLocation, glBindBuffer, glBufferData,
                       glClear, glClearColor, glCompileShader, glCreateProgram,
                       glCreateShader, glDeleteShader, glDisable,
                       glDisableVertexAttribArray, glDrawArrays,
                       glEnableVertexAttribArray, glGenBuffers,
                       glGetProgramInfoLog, glGetProgramiv, glGetShaderInfoLog,
                       glGetShaderiv, glGetUniformLocation, glLinkProgram,
                       glPixelStorei, glReadPixels, glShaderSource,
                       glUniform1f, glUniform2f, glUseProgram,
                       glVertexAttribPointer, glViewport)

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.cloth_sail.provider import ClothSailStateProvider
from heart.renderers.cloth_sail.state import ClothSailState

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
uniform vec2 u_wind;

varying vec2 v_uv;

const vec3 COLOR_CANVAS = vec3(0.93, 0.88, 0.76);
const vec3 COLOR_NAVY = vec3(0.12, 0.24, 0.41);
const vec3 COLOR_RUST = vec3(0.53, 0.29, 0.21);
const vec3 LIGHT_DIR = vec3(-0.38, 0.42, 0.82);

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float weave(vec2 uv) {
    vec2 loom = uv * vec2(u_resolution.x / 4.0, u_resolution.y);
    float warp = sin(loom.x * 0.012 + loom.y * 0.05);
    float weft = sin(loom.y * 0.05 + loom.x * 0.03);
    return (warp * weft) * 0.02;
}

float gust_noise(vec2 uv, float t) {
    vec2 s = floor(uv * vec2(6.0, 3.0));
    vec2 f = fract(uv * vec2(6.0, 3.0));
    float a = hash(s + vec2(0.0, 0.0));
    float b = hash(s + vec2(1.0, 0.0));
    float c = hash(s + vec2(0.0, 1.0));
    float d = hash(s + vec2(1.0, 1.0));
    float lerp_x1 = mix(a, b, f.x);
    float lerp_x2 = mix(c, d, f.x);
    float gust = mix(lerp_x1, lerp_x2, f.y);
    return gust * 0.08 * sin(t * 0.9);
}

float cloth_height(vec2 uv, float t) {
    float anchor = smoothstep(0.05, 0.2, uv.y);
    float edge = smoothstep(0.02, 0.12, uv.x) * smoothstep(0.02, 0.12, 1.0 - uv.x);

    float wave_travel = sin((uv.x * 4.5 - t * (1.2 + u_wind.x)) + sin(uv.y * 7.0 + t)) * 0.22;
    float ripple = sin(uv.y * 10.0 + t * 1.6) * 0.05;
    float cross = sin((uv.x + uv.y * 0.6) * 6.0 - t * 0.8) * 0.04;
    float lean = u_wind.x * (uv.x - 0.5) * 0.45;
    float sag = -0.12 * smoothstep(0.0, 1.0, uv.y) * smoothstep(0.0, 1.0, uv.y);

    float gust = gust_noise(uv + vec2(t * 0.03, t * 0.05), t);

    return lean + (wave_travel + ripple + cross + gust) * anchor * edge + sag;
}

vec3 cloth_position(vec2 uv, float t) {
    float height = cloth_height(uv, t);
    float span = 1.2;
    float drop = 0.6;
    return vec3((uv.x - 0.5) * span, (uv.y - 0.5) * drop, height);
}

vec3 cloth_normal(vec2 uv, float t) {
    float eps = 1.5 / max(u_resolution.x, 120.0);
    vec3 pos = cloth_position(uv, t);
    vec3 pos_dx = cloth_position(uv + vec2(eps, 0.0), t);
    vec3 pos_dy = cloth_position(uv + vec2(0.0, eps), t);
    vec3 tangent_x = pos_dx - pos;
    vec3 tangent_y = pos_dy - pos;
    return normalize(cross(tangent_y, tangent_x));
}

vec3 palette(vec2 uv) {
    float stripes = smoothstep(0.2, 0.7, sin((uv.y + 0.03) * 3.14159 * 6.0));
    stripes = mix(stripes, 1.0 - stripes, smoothstep(0.6, 0.9, uv.x));
    vec3 base = mix(COLOR_CANVAS, COLOR_NAVY, stripes);
    float hem = smoothstep(0.0, 0.02, uv.y) * (1.0 - smoothstep(0.04, 0.08, uv.y));
    base = mix(base, COLOR_RUST, hem * 0.6);
    float rope = smoothstep(0.0, 0.03, uv.x) * (1.0 - smoothstep(0.05, 0.08, uv.x));
    rope += smoothstep(0.0, 0.03, 1.0 - uv.x) * (1.0 - smoothstep(0.05, 0.08, 1.0 - uv.x));
    base += rope * vec3(0.62, 0.48, 0.31);
    base += weave(uv) * vec3(1.0);
    return base;
}

void main() {
    float t = u_time;
    vec2 uv = v_uv;

    vec3 normal = cloth_normal(uv, t);
    vec3 base_color = palette(uv);

    float diffuse = max(dot(normal, normalize(LIGHT_DIR)), 0.0);
    float grazing = pow(1.0 - max(dot(normal, vec3(0.0, 0.0, 1.0)), 0.0), 1.5);
    vec3 highlight = vec3(0.8, 0.85, 0.9) * pow(max(0.0, dot(reflect(-normalize(LIGHT_DIR), normal), vec3(0.0, 0.0, 1.0))), 12.0);

    float ambient = 0.35;
    vec3 color = base_color * (ambient + diffuse * 0.85);
    color += grazing * vec3(0.18, 0.2, 0.26);
    color += highlight * 0.6;

    vec3 sea = mix(vec3(0.12, 0.19, 0.27), vec3(0.24, 0.33, 0.38), uv.y);
    float edge = smoothstep(0.0, 0.05, min(min(uv.x, 1.0 - uv.x), uv.y));
    color = mix(sea * (0.6 + 0.4 * diffuse), color, edge);

    gl_FragColor = vec4(color, 1.0);
}
"""


class ClothSailRenderer(StatefulBaseRenderer[ClothSailState]):
    """Render a farmhouse-nautical cloth waving across the four panels."""

    def __init__(self, builder: ClothSailStateProvider | None = None) -> None:
        self._builder: ClothSailStateProvider | None = builder
        super().__init__(builder=builder)  # type: ignore[arg-type]
        self.device_display_mode = DeviceDisplayMode.OPENGL
        self.warmup = False
        self.set_state(ClothSailState())

        self._program: Optional[int] = None
        self._vertex_buffer: Optional[int] = None
        self._quad_vertices = np.array(
            [-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0], dtype=np.float32
        )

        self._uniform_time: Optional[int] = None
        self._uniform_resolution: Optional[int] = None
        self._uniform_wind: Optional[int] = None
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
        if drawable_width <= 0 or drawable_height <= 0:
            return window.get_size()

        return int(drawable_width), int(drawable_height)

    def _compile_shader(self, source: str, shader_type: int) -> int:
        shader = glCreateShader(shader_type)
        glShaderSource(shader, source)
        glCompileShader(shader)
        compile_status = glGetShaderiv(shader, GL_COMPILE_STATUS)
        if not compile_status:
            raise RuntimeError(glGetShaderInfoLog(shader).decode("utf-8"))
        return shader

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if self._program is None:
            vertex_shader = self._compile_shader(VERT_SHADER, GL_VERTEX_SHADER)
            fragment_shader = self._compile_shader(FRAG_SHADER, GL_FRAGMENT_SHADER)

            program = glCreateProgram()
            glAttachShader(program, vertex_shader)
            glAttachShader(program, fragment_shader)
            glBindAttribLocation(program, 0, "a_position")
            glLinkProgram(program)

            link_status = glGetProgramiv(program, GL_LINK_STATUS)
            if not link_status:
                info = glGetProgramInfoLog(program).decode("utf-8")
                glDeleteShader(vertex_shader)
                glDeleteShader(fragment_shader)
                raise RuntimeError(f"Shader link failed: {info}")

            glDeleteShader(vertex_shader)
            glDeleteShader(fragment_shader)

            self._program = program
            glUseProgram(self._program)

            self._uniform_time = glGetUniformLocation(self._program, "u_time")
            self._uniform_resolution = glGetUniformLocation(
                self._program, "u_resolution"
            )
            self._uniform_wind = glGetUniformLocation(self._program, "u_wind")

            self._vertex_buffer = glGenBuffers(1)
            glBindBuffer(GL_ARRAY_BUFFER, self._vertex_buffer)
            glBufferData(
                GL_ARRAY_BUFFER,
                self._quad_vertices.nbytes,
                self._quad_vertices,
                GL_STATIC_DRAW,
            )

            glEnableVertexAttribArray(0)
            glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, None)

            glPixelStorei(GL_PACK_ALIGNMENT, 1)
            glDisable(GL_DEPTH_TEST)
            glDisable(GL_CULL_FACE)

        super().initialize(window, clock, peripheral_manager, orientation)

    def state_observable(
        self, peripheral_manager: PeripheralManager
    ) -> reactivex.Observable[ClothSailState]:
        if self._builder is None:
            self._builder = ClothSailStateProvider(peripheral_manager)
            self.builder = self._builder

        return self._builder.observable()

    def _ensure_pixel_buffer(self, size: tuple[int, int]) -> None:
        width, height = size
        if (
            self._pixel_buffer is None
            or self._pixel_buffer.shape[0] != height
            or self._pixel_buffer.shape[1] != width
        ):
            self._pixel_buffer = np.zeros((height, width, 3), dtype=np.uint8)

    def real_process(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        surface_width, surface_height = window.get_size()
        if surface_width == 0 or surface_height == 0:
            return

        frame_width, frame_height = self._get_drawable_size(window)
        if frame_width == 0 or frame_height == 0:
            return

        self._ensure_pixel_buffer((frame_width, frame_height))

        elapsed = self.state.elapsed_seconds

        wind_strength = 0.7 + 0.25 * math.sin(elapsed * 0.3)
        wind_vertical = 0.08 * math.sin(elapsed * 0.6 + 1.2)

        glUseProgram(self._program)
        glUniform1f(self._uniform_time, float(elapsed))
        glUniform2f(self._uniform_resolution, float(frame_width), float(frame_height))
        glUniform2f(self._uniform_wind, wind_strength, wind_vertical)

        glViewport(0, 0, frame_width, frame_height)
        glClearColor(0.07, 0.1, 0.15, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)

        glBindBuffer(GL_ARRAY_BUFFER, self._vertex_buffer)
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

        flipped = np.flipud(self._pixel_buffer)
        frame_array = np.transpose(flipped, (1, 0, 2))
        frame_array = np.ascontiguousarray(frame_array)

        if (frame_width, frame_height) == (surface_width, surface_height):
            pygame.surfarray.blit_array(window, frame_array)
        else:
            frame_surface = pygame.surfarray.make_surface(frame_array)
            scaled_surface = pygame.transform.smoothscale(
                frame_surface, (surface_width, surface_height)
            )
            window.blit(scaled_surface, (0, 0))
