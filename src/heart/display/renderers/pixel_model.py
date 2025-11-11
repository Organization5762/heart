"""Pixelated renderer that projects arbitrary 3D meshes into 2D output."""

from __future__ import annotations

import ctypes
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
import pygame
from OpenGL.GL import (GL_ARRAY_BUFFER, GL_COLOR_BUFFER_BIT, GL_COMPILE_STATUS,
                       GL_DEPTH_BUFFER_BIT, GL_DEPTH_TEST, GL_FALSE, GL_FLOAT,
                       GL_FRAGMENT_SHADER, GL_LEQUAL, GL_LINK_STATUS, GL_RGB,
                       GL_STATIC_DRAW, GL_TRIANGLES, GL_TRUE, GL_UNSIGNED_BYTE,
                       GL_VERTEX_SHADER, glAttachShader, glBindAttribLocation,
                       glBindBuffer, glBufferData, glClear, glClearColor,
                       glClearDepth, glCompileShader, glCreateProgram,
                       glCreateShader, glDeleteProgram, glDeleteShader,
                       glDepthFunc, glDisableVertexAttribArray, glDrawArrays,
                       glEnable, glEnableVertexAttribArray, glGenBuffers,
                       glGetProgramInfoLog, glGetProgramiv, glGetShaderInfoLog,
                       glGetShaderiv, glGetUniformLocation, glLinkProgram,
                       glReadPixels, glShaderSource, glUniform1f, glUniform2f,
                       glUniform3f, glUniformMatrix3fv, glUniformMatrix4fv,
                       glUseProgram, glVertexAttribPointer, glViewport)

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.display.renderers import BaseRenderer
from heart.peripheral.core.manager import PeripheralManager

VERT_SHADER = """
#version 120

attribute vec3 a_position;
attribute vec3 a_normal;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_proj;
uniform mat3 u_normal_matrix;

varying vec3 v_position;
varying vec3 v_normal;

void main() {
    vec4 world = u_model * vec4(a_position, 1.0);
    v_position = world.xyz;
    v_normal = normalize(u_normal_matrix * a_normal);
    gl_Position = u_proj * u_view * world;
}
"""


FRAG_SHADER = """
#version 120

uniform float u_time;
uniform vec2 u_resolution;
uniform vec3 u_camera_pos;
uniform vec3 u_light_direction;
uniform vec3 u_diffuse_tint;
uniform vec3 u_specular_tint;
uniform vec3 u_ambient_tint;
uniform float u_palette_levels;
uniform float u_pixel_rows;

varying vec3 v_position;
varying vec3 v_normal;

const float PI = 3.14159265358979;

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

vec3 palette(vec3 base_color, vec3 light, float palette_levels, vec2 frag_coord, vec2 resolution, float pixel_rows) {
    float step_y = max(1.0, floor(resolution.y / pixel_rows));
    float step_x = max(1.0, floor(resolution.x / (resolution.y / step_y * pixel_rows)));
    vec2 cell = floor(vec2(frag_coord.x / step_x, frag_coord.y / step_y));
    float dither = hash(cell);
    vec3 lit = clamp(base_color * light, 0.0, 1.0);
    return floor(lit * palette_levels + dither * 0.75) / palette_levels;
}

void main() {
    vec3 normal = normalize(v_normal);
    vec3 view_dir = normalize(u_camera_pos - v_position);
    vec3 light_dir = normalize(u_light_direction);

    float diffuse = max(dot(normal, light_dir), 0.0);
    vec3 halfway = normalize(light_dir + view_dir);
    float specular = pow(max(dot(normal, halfway), 0.0), 32.0);

    float rim = pow(1.0 - max(dot(normal, view_dir), 0.0), 2.5);
    float height = clamp((v_position.y + 1.0) * 0.5, 0.0, 1.0);
    vec3 base = mix(u_diffuse_tint * 0.7, u_diffuse_tint * 1.2, height);
    base += vec3(0.08, 0.06, 0.04) * sin(u_time * 0.5 + v_position.x * 1.2);

    vec3 lighting = u_ambient_tint + diffuse * u_diffuse_tint + specular * u_specular_tint + rim * u_ambient_tint * 0.5;
    vec3 color = palette(base, lighting, u_palette_levels, gl_FragCoord.xy, u_resolution, u_pixel_rows);

    gl_FragColor = vec4(color, 1.0);
}
"""


@dataclass
class _Mesh:
    vertex_buffer: int
    vertex_count: int
    center: np.ndarray
    scale: float


class PixelModelRenderer(BaseRenderer):
    """Render arbitrary OBJ meshes with a quantised, pixel-art aesthetic."""

    def __init__(
        self,
        model_path: str | Path,
        *,
        target_rows: int = 96,
        palette_levels: int = 6,
    ) -> None:
        super().__init__()
        self.device_display_mode = DeviceDisplayMode.OPENGL
        self.warmup = False

        self.model_path = Path(model_path)
        self.target_rows = float(target_rows)
        self.palette_levels = float(palette_levels)

        self._program: Optional[int] = None
        self._mesh: Optional[_Mesh] = None
        self._pixel_buffer: Optional[np.ndarray] = None
        self._start_time: float | None = None

        self._uniform_model: Optional[int] = None
        self._uniform_view: Optional[int] = None
        self._uniform_proj: Optional[int] = None
        self._uniform_normal_matrix: Optional[int] = None
        self._uniform_time: Optional[int] = None
        self._uniform_resolution: Optional[int] = None
        self._uniform_camera_pos: Optional[int] = None
        self._uniform_light_dir: Optional[int] = None
        self._uniform_palette_levels: Optional[int] = None
        self._uniform_pixel_rows: Optional[int] = None
        self._uniform_diffuse_tint: Optional[int] = None
        self._uniform_specular_tint: Optional[int] = None
        self._uniform_ambient_tint: Optional[int] = None

    # ----- math helpers -----
    @staticmethod
    def _perspective(fovy_radians: float, aspect: float, near: float, far: float) -> np.ndarray:
        f = 1.0 / math.tan(fovy_radians / 2.0)
        depth = near - far
        return np.array(
            [
                [f / aspect, 0.0, 0.0, 0.0],
                [0.0, f, 0.0, 0.0],
                [0.0, 0.0, (far + near) / depth, (2.0 * far * near) / depth],
                [0.0, 0.0, -1.0, 0.0],
            ],
            dtype=np.float32,
        )

    @staticmethod
    def _look_at(eye: np.ndarray, target: np.ndarray, up: np.ndarray) -> np.ndarray:
        forward = target - eye
        forward = forward / np.linalg.norm(forward)
        right = np.cross(forward, up)
        right = right / np.linalg.norm(right)
        true_up = np.cross(right, forward)
        view = np.eye(4, dtype=np.float32)
        view[0, :3] = right
        view[1, :3] = true_up
        view[2, :3] = -forward
        view[:3, 3] = -np.dot(view[:3, :3], eye)
        return view

    @staticmethod
    def _normalize_vectors(vectors: Iterable[np.ndarray]) -> np.ndarray:
        stacked = np.stack(list(vectors), axis=0)
        norms = np.linalg.norm(stacked, axis=1, keepdims=True)
        norms[norms == 0.0] = 1.0
        return stacked / norms

    # ----- resource helpers -----
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
        glBindAttribLocation(program, 1, "a_normal")
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

    # ----- mesh loading -----
    @staticmethod
    def _parse_face(tokens: list[str]) -> list[tuple[int, Optional[int]]]:
        vertices: list[tuple[int, Optional[int]]] = []
        for token in tokens:
            parts = token.split("/")
            position_index = int(parts[0]) - 1
            normal_index = int(parts[2]) - 1 if len(parts) >= 3 and parts[2] else None
            vertices.append((position_index, normal_index))
        if len(vertices) == 4:
            # Triangulate quad into two triangles (0,1,2) and (0,2,3)
            return [vertices[0], vertices[1], vertices[2], vertices[0], vertices[2], vertices[3]]
        return vertices

    def _load_mesh(self) -> _Mesh:
        if not self.model_path.exists():
            raise FileNotFoundError(f"OBJ model not found: {self.model_path}")

        positions: list[np.ndarray] = []
        normals: list[np.ndarray] = []
        faces: list[tuple[int, Optional[int]]] = []

        with self.model_path.open("r", encoding="utf8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if stripped.startswith("v "):
                    _, x, y, z = stripped.split()
                    positions.append(np.array([float(x), float(y), float(z)], dtype=np.float32))
                elif stripped.startswith("vn "):
                    _, x, y, z = stripped.split()
                    normals.append(np.array([float(x), float(y), float(z)], dtype=np.float32))
                elif stripped.startswith("f "):
                    tokens = stripped.split()[1:]
                    faces.extend(self._parse_face(tokens))

        if not positions:
            raise ValueError(f"Model {self.model_path} contains no vertices")

        if not normals:
            normals = [np.zeros(3, dtype=np.float32) for _ in positions]

        if any(normal is None for _, normal in faces):
            # Compute flat normals for faces missing them.
            computed_normals = [np.zeros(3, dtype=np.float32) for _ in positions]
            counts = [0] * len(positions)
            for i in range(0, len(faces), 3):
                i0, n0 = faces[i]
                i1, n1 = faces[i + 1]
                i2, n2 = faces[i + 2]
                p0, p1, p2 = positions[i0], positions[i1], positions[i2]
                face_normal = np.cross(p1 - p0, p2 - p0)
                norm = np.linalg.norm(face_normal)
                if norm > 0:
                    face_normal = face_normal / norm
                else:
                    face_normal = np.array([0.0, 1.0, 0.0], dtype=np.float32)
                for idx in (i0, i1, i2):
                    computed_normals[idx] += face_normal
                    counts[idx] += 1
                faces[i] = (i0, n0 if n0 is not None else i0)
                faces[i + 1] = (i1, n1 if n1 is not None else i1)
                faces[i + 2] = (i2, n2 if n2 is not None else i2)
            for idx, normal in enumerate(computed_normals):
                if counts[idx] > 0:
                    normal /= counts[idx]
                normals[idx] = normal.astype(np.float32)

        vertices: list[float] = []
        bounds_min = np.min(np.stack(positions, axis=0), axis=0)
        bounds_max = np.max(np.stack(positions, axis=0), axis=0)
        center = (bounds_min + bounds_max) / 2.0
        extent = np.max(bounds_max - bounds_min)
        scale = 2.0 / extent if extent > 0.0 else 1.0

        for position_index, normal_index in faces:
            pos = positions[position_index]
            norm = normals[normal_index if normal_index is not None else position_index]
            vertices.extend([pos[0], pos[1], pos[2], norm[0], norm[1], norm[2]])

        vertex_array = np.array(vertices, dtype=np.float32)
        vertex_buffer = glGenBuffers(1)  # type: ignore[no-untyped-call]
        glBindBuffer(GL_ARRAY_BUFFER, vertex_buffer)
        glBufferData(GL_ARRAY_BUFFER, vertex_array.nbytes, vertex_array, GL_STATIC_DRAW)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

        vertex_count = len(vertex_array) // 6
        return _Mesh(vertex_buffer=vertex_buffer, vertex_count=vertex_count, center=center, scale=scale)

    # ----- renderer lifecycle -----
    def _ensure_pixel_buffer(self, size: tuple[int, int]) -> None:
        width, height = size
        if (
            self._pixel_buffer is None
            or self._pixel_buffer.shape[0] != height
            or self._pixel_buffer.shape[1] != width
        ):
            self._pixel_buffer = np.zeros((height, width, 3), dtype=np.uint8)

    def initialize(
        self,
        window: pygame.Surface,
        clock: pygame.time.Clock,
        peripheral_manager: PeripheralManager,
        orientation: Orientation,
    ) -> None:
        if self._program is None:
            self._program = self._create_program()
            glUseProgram(self._program)
            self._uniform_model = glGetUniformLocation(self._program, "u_model")
            self._uniform_view = glGetUniformLocation(self._program, "u_view")
            self._uniform_proj = glGetUniformLocation(self._program, "u_proj")
            self._uniform_normal_matrix = glGetUniformLocation(self._program, "u_normal_matrix")
            self._uniform_time = glGetUniformLocation(self._program, "u_time")
            self._uniform_resolution = glGetUniformLocation(self._program, "u_resolution")
            self._uniform_camera_pos = glGetUniformLocation(self._program, "u_camera_pos")
            self._uniform_light_dir = glGetUniformLocation(self._program, "u_light_direction")
            self._uniform_palette_levels = glGetUniformLocation(self._program, "u_palette_levels")
            self._uniform_pixel_rows = glGetUniformLocation(self._program, "u_pixel_rows")
            self._uniform_diffuse_tint = glGetUniformLocation(self._program, "u_diffuse_tint")
            self._uniform_specular_tint = glGetUniformLocation(self._program, "u_specular_tint")
            self._uniform_ambient_tint = glGetUniformLocation(self._program, "u_ambient_tint")

        if self._mesh is None:
            self._mesh = self._load_mesh()

        if self._start_time is None:
            self._start_time = time.perf_counter()

        glUseProgram(self._program)
        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LEQUAL)  # type: ignore[no-untyped-call]
        glClearDepth(1.0)  # type: ignore[no-untyped-call]

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

        if self._mesh is None or self._mesh.vertex_count == 0:
            return

        surface_width, surface_height = window.get_size()
        if surface_width == 0 or surface_height == 0:
            return

        frame_width, frame_height = surface_width, surface_height
        self._ensure_pixel_buffer((frame_width, frame_height))

        start_time = self._start_time or time.perf_counter()
        elapsed = time.perf_counter() - start_time

        glUseProgram(self._program)

        if self._uniform_time is not None:
            glUniform1f(self._uniform_time, float(elapsed))
        if self._uniform_resolution is not None:
            glUniform2f(self._uniform_resolution, float(frame_width), float(frame_height))
        if self._uniform_palette_levels is not None:
            glUniform1f(self._uniform_palette_levels, self.palette_levels)
        if self._uniform_pixel_rows is not None:
            glUniform1f(self._uniform_pixel_rows, self.target_rows)

        mesh = self._mesh
        camera_radius = 3.0
        orbit_speed = 0.35
        angle = elapsed * orbit_speed
        eye = np.array(
            [
                math.sin(angle) * camera_radius,
                1.2,
                math.cos(angle) * camera_radius,
            ],
            dtype=np.float32,
        )
        target = np.zeros(3, dtype=np.float32)
        up = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        view = self._look_at(eye, target, up)
        aspect = frame_width / frame_height
        proj = self._perspective(math.radians(50.0), aspect, 0.1, 20.0)

        rotation = math.radians(25.0)
        model = np.eye(4, dtype=np.float32)
        model[:3, :3] = [
            [math.cos(rotation), 0.0, math.sin(rotation)],
            [0.0, 1.0, 0.0],
            [-math.sin(rotation), 0.0, math.cos(rotation)],
        ]
        model[:3, 3] = -mesh.center
        model[:3, :3] *= mesh.scale
        normal_matrix = np.linalg.inv(model[:3, :3]).T.astype(np.float32)

        if self._uniform_model is not None:
            glUniformMatrix4fv(self._uniform_model, 1, GL_FALSE, model)
        if self._uniform_view is not None:
            glUniformMatrix4fv(self._uniform_view, 1, GL_FALSE, view)
        if self._uniform_proj is not None:
            glUniformMatrix4fv(self._uniform_proj, 1, GL_FALSE, proj)
        if self._uniform_normal_matrix is not None:
            glUniformMatrix3fv(self._uniform_normal_matrix, 1, GL_FALSE, normal_matrix)
        if self._uniform_camera_pos is not None:
            glUniform3f(self._uniform_camera_pos, float(eye[0]), float(eye[1]), float(eye[2]))
        if self._uniform_light_dir is not None:
            light_dir = np.array([-0.4, 1.0, 0.6], dtype=np.float32)
            norm = np.linalg.norm(light_dir)
            if norm > 0:
                light_dir /= norm
            glUniform3f(self._uniform_light_dir, float(light_dir[0]), float(light_dir[1]), float(light_dir[2]))
        if self._uniform_diffuse_tint is not None:
            glUniform3f(self._uniform_diffuse_tint, 0.85, 0.55, 0.55)
        if self._uniform_specular_tint is not None:
            glUniform3f(self._uniform_specular_tint, 0.9, 0.8, 0.7)
        if self._uniform_ambient_tint is not None:
            glUniform3f(self._uniform_ambient_tint, 0.3, 0.3, 0.35)

        glViewport(0, 0, frame_width, frame_height)
        glClearColor(0.05, 0.07, 0.12, 1.0)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        glBindBuffer(GL_ARRAY_BUFFER, mesh.vertex_buffer)
        glEnableVertexAttribArray(0)
        glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 24, ctypes.c_void_p(0))
        glEnableVertexAttribArray(1)
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 24, ctypes.c_void_p(12))
        glDrawArrays(GL_TRIANGLES, 0, mesh.vertex_count)
        glDisableVertexAttribArray(0)
        glDisableVertexAttribArray(1)
        glBindBuffer(GL_ARRAY_BUFFER, 0)

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
        frame_surface = pygame.surfarray.make_surface(frame_array)
        if (frame_width, frame_height) != (surface_width, surface_height):
            frame_surface = pygame.transform.smoothscale(frame_surface, (surface_width, surface_height))
        window.blit(frame_surface, (0, 0))

        clock.tick_busy_loop(60)

