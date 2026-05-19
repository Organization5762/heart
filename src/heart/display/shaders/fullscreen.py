from __future__ import annotations

from ctypes import byref, c_int
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np
import pygame
from OpenGL.error import GLError
from OpenGL.GL import (GL_COLOR_BUFFER_BIT, GL_COMPILE_STATUS,
                       GL_DEPTH_BUFFER_BIT, GL_FLOAT, GL_FRAGMENT_SHADER,
                       GL_INFO_LOG_LENGTH, GL_LINK_STATUS, GL_RGBA,
                       GL_TEXTURE0, GL_TEXTURE_2D, GL_TRIANGLE_STRIP,
                       GL_UNSIGNED_BYTE, GL_VERTEX_SHADER, glActiveTexture,
                       glAttachShader, glBindAttribLocation, glBindTexture,
                       glClear, glCompileShader, glCreateProgram,
                       glCreateShader, glDeleteProgram, glDeleteShader,
                       glDrawArrays, glEnableVertexAttribArray,
                       glGetProgramInfoLog, glGetProgramiv, glGetShaderInfoLog,
                       glGetShaderiv, glGetUniformLocation, glLinkProgram,
                       glReadPixels, glShaderSource, glUniform1f, glUniform1i,
                       glUniform2fv, glUniform3fv, glUniform4fv,
                       glUniformMatrix4fv, glUseProgram, glVertexAttribPointer,
                       glViewport)

from heart.runtime.display_context import DisplayContext
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class TextureUniform:
    texture_id: int
    texture_unit: int = 0
    target: int = GL_TEXTURE_2D


UniformValue = (
    float | int | tuple[float, ...] | list[float] | np.ndarray | TextureUniform
)
DEFAULT_VERTEX_SHADER = """#version 120
attribute vec4 vPosition;
void main() {
    gl_Position = vPosition;
}
"""


class FullscreenShaderRuntime:
    def __init__(self) -> None:
        self.program: int | None = None
        self.uniform_locations: dict[str, int] = {}
        self.pixel_buffer: np.ndarray | None = None
        self._quad_vertices = np.array(
            [-1.0, -1.0, 0.0, 1.0, -1.0, 0.0, -1.0, 1.0, 0.0, 1.0, 1.0, 0.0],
            dtype=np.float32,
        )

    def initialize(
        self,
        *,
        fragment_source: str | None = None,
        fragment_path: str | Path | None = None,
        vertex_source: str | None = None,
        vertex_path: str | Path | None = None,
        attribute_name: str = "vPosition",
    ) -> None:
        resolved_vertex_source = self._resolve_source(
            source=vertex_source,
            path=vertex_path,
            fallback=DEFAULT_VERTEX_SHADER,
        )
        resolved_fragment_source = self._resolve_source(
            source=fragment_source,
            path=fragment_path,
            fallback=None,
        )
        if resolved_fragment_source is None:
            raise ValueError("FullscreenShaderRuntime requires a fragment shader")

        self.program = self._compile_program(
            vertex_source=resolved_vertex_source,
            fragment_source=resolved_fragment_source,
            attribute_name=attribute_name,
        )
        glUseProgram(self.program)
        glVertexAttribPointer(0, 3, GL_FLOAT, False, 0, self._quad_vertices)
        glEnableVertexAttribArray(0)

    def is_initialized(self) -> bool:
        return self.program is not None

    def draw(
        self,
        *,
        uniforms: Mapping[str, UniformValue],
        viewport_size: tuple[int, int],
        viewport_origin: tuple[int, int] = (0, 0),
        clear_mask: int | None = GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT,
    ) -> None:
        if self.program is None:
            raise RuntimeError("FullscreenShaderRuntime is not initialized")
        glUseProgram(self.program)
        width, height = viewport_size
        origin_x, origin_y = viewport_origin
        glViewport(origin_x, origin_y, width, height)
        if clear_mask is not None:
            glClear(clear_mask)
        self.apply_uniforms(uniforms)
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)

    def render(
        self,
        window: DisplayContext,
        *,
        uniforms: Mapping[str, UniformValue],
        viewport_size: tuple[int, int] | None = None,
        clear_mask: int | None = GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT,
    ) -> None:
        size = viewport_size or window.get_size()
        self.draw(uniforms=uniforms, viewport_size=size, clear_mask=clear_mask)
        self.read_to_surface(window, size=size)

    def read_to_surface(
        self,
        window: DisplayContext,
        *,
        size: tuple[int, int] | None = None,
    ) -> None:
        frame_surface = self.read_surface(size=size or window.get_size())
        surface_size = window.get_size()
        if surface_size == frame_surface.get_size():
            window.blit(frame_surface, (0, 0))
            return
        scaled_surface = pygame.transform.smoothscale(frame_surface, surface_size)
        window.blit(scaled_surface, (0, 0))

    def read_surface(self, *, size: tuple[int, int]) -> pygame.Surface:
        width, height = size
        self._ensure_pixel_buffer(width=width, height=height)
        assert self.pixel_buffer is not None
        glReadPixels(
            0,
            0,
            width,
            height,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            self.pixel_buffer,
        )
        frame_array = np.transpose(np.flipud(self.pixel_buffer[:, :, :3]), (1, 0, 2))
        return pygame.surfarray.make_surface(np.ascontiguousarray(frame_array))

    def apply_uniforms(self, uniforms: Mapping[str, UniformValue]) -> None:
        for name, value in uniforms.items():
            location = self.uniform_location(name)
            self._apply_uniform(location, value)

    def uniform_location(self, name: str) -> int:
        if self.program is None:
            raise RuntimeError("FullscreenShaderRuntime is not initialized")
        if name not in self.uniform_locations:
            self.uniform_locations[name] = glGetUniformLocation(self.program, name)
        return self.uniform_locations[name]

    def reset(self) -> None:
        if self.program is not None:
            try:
                glDeleteProgram(self.program)
            except GLError:
                logger.debug("Skipping shader program delete; OpenGL context is unavailable")
        self.program = None
        self.uniform_locations.clear()
        self.pixel_buffer = None

    def _ensure_pixel_buffer(self, *, width: int, height: int) -> None:
        if (
            self.pixel_buffer is None
            or self.pixel_buffer.shape[0] != height
            or self.pixel_buffer.shape[1] != width
        ):
            self.pixel_buffer = np.zeros((height, width, 4), dtype=np.uint8)

    @staticmethod
    def _resolve_source(
        *,
        source: str | None,
        path: str | Path | None,
        fallback: str | None,
    ) -> str | None:
        if source is not None and path is not None:
            raise ValueError("Provide source or path, not both")
        if source is not None:
            return source
        if path is not None:
            return Path(path).read_text(encoding="utf-8")
        return fallback

    @staticmethod
    def _compile_shader(source: str, shader_type: int) -> int:
        shader = glCreateShader(shader_type)
        glShaderSource(shader, source)
        glCompileShader(shader)
        status = c_int()
        glGetShaderiv(shader, GL_COMPILE_STATUS, byref(status))
        if not status.value:
            info_log = FullscreenShaderRuntime._shader_info_log(shader)
            glDeleteShader(shader)
            raise RuntimeError(f"Shader compilation failed: {info_log}")
        return shader

    @staticmethod
    def _compile_program(
        *,
        vertex_source: str,
        fragment_source: str,
        attribute_name: str,
    ) -> int:
        vertex_shader = FullscreenShaderRuntime._compile_shader(
            vertex_source, GL_VERTEX_SHADER
        )
        fragment_shader = FullscreenShaderRuntime._compile_shader(
            fragment_source, GL_FRAGMENT_SHADER
        )
        program = glCreateProgram()
        glAttachShader(program, vertex_shader)
        glAttachShader(program, fragment_shader)
        glBindAttribLocation(program, 0, attribute_name)
        glLinkProgram(program)
        glDeleteShader(vertex_shader)
        glDeleteShader(fragment_shader)
        link_status = glGetProgramiv(program, GL_LINK_STATUS)
        if not link_status:
            info = glGetProgramInfoLog(program)
            if isinstance(info, bytes):
                info = info.decode("utf-8", errors="replace")
            raise RuntimeError(f"Shader link failed: {info}")
        return program

    @staticmethod
    def _shader_info_log(shader: int) -> str:
        length = c_int()
        glGetShaderiv(shader, GL_INFO_LOG_LENGTH, byref(length))
        if length.value <= 0:
            return ""
        info_log = glGetShaderInfoLog(shader)
        if isinstance(info_log, bytes):
            return info_log.decode("utf-8", errors="replace")
        return str(info_log)

    @staticmethod
    def _apply_uniform(location: int, value: UniformValue) -> None:
        if isinstance(value, TextureUniform):
            glActiveTexture(GL_TEXTURE0 + value.texture_unit)
            glBindTexture(value.target, value.texture_id)
            glUniform1i(location, value.texture_unit)
            return
        if isinstance(value, (float, int)):
            glUniform1f(location, float(value))
            return
        array = np.asarray(value, dtype=np.float32)
        if array.shape == (4, 4):
            glUniformMatrix4fv(location, 1, False, array)
            return
        flattened = array.reshape(-1)
        if flattened.shape == (2,):
            glUniform2fv(location, 1, flattened)
            return
        if flattened.shape == (3,):
            glUniform3fv(location, 1, flattened)
            return
        if flattened.shape == (4,):
            glUniform4fv(location, 1, flattened)
            return
        raise ValueError(f"Unsupported uniform value shape for location {location}")
