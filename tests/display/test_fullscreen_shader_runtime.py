"""Validate reusable fullscreen shader runtime helpers."""

from __future__ import annotations

from typing import Any

import numpy as np
import pygame

from heart.device import Rectangle
from heart.device.local import LocalScreen
from heart.display.shaders import fullscreen as fullscreen_module
from heart.display.shaders.fullscreen import FullscreenShaderRuntime, TextureUniform
from heart.runtime.display_context import DisplayContext


def _make_window(width: int = 2, height: int = 2) -> DisplayContext:
    orientation = Rectangle.with_layout(columns=1, rows=1)
    device = LocalScreen(width=width, height=height, orientation=orientation)
    return DisplayContext(
        device=device,
        screen=pygame.Surface(device.full_display_size()),
        clock=pygame.time.Clock(),
    )


def _install_compile_stubs(monkeypatch) -> dict[str, list[Any]]:
    calls: dict[str, list[Any]] = {
        "attrib": [],
        "uniform1f": [],
        "uniform2fv": [],
        "uniform3fv": [],
        "uniform4fv": [],
        "uniform_matrix4fv": [],
        "uniform1i": [],
        "active_texture": [],
        "bind_texture": [],
        "draw": [],
    }
    monkeypatch.setattr(fullscreen_module, "glCreateShader", lambda shader_type: shader_type)
    monkeypatch.setattr(fullscreen_module, "glShaderSource", lambda *_args: None)
    monkeypatch.setattr(fullscreen_module, "glCompileShader", lambda *_args: None)

    def set_shader_status(_shader, _pname, status) -> None:
        status._obj.value = 1

    monkeypatch.setattr(fullscreen_module, "glGetShaderiv", set_shader_status)
    monkeypatch.setattr(fullscreen_module, "glCreateProgram", lambda: 101)
    monkeypatch.setattr(fullscreen_module, "glAttachShader", lambda *_args: None)
    monkeypatch.setattr(
        fullscreen_module,
        "glBindAttribLocation",
        lambda *args: calls["attrib"].append(args),
    )
    monkeypatch.setattr(fullscreen_module, "glLinkProgram", lambda *_args: None)
    monkeypatch.setattr(fullscreen_module, "glDeleteShader", lambda *_args: None)
    monkeypatch.setattr(fullscreen_module, "glGetProgramiv", lambda *_args: 1)
    monkeypatch.setattr(fullscreen_module, "glUseProgram", lambda *_args: None)
    monkeypatch.setattr(fullscreen_module, "glVertexAttribPointer", lambda *_args: None)
    monkeypatch.setattr(fullscreen_module, "glEnableVertexAttribArray", lambda *_args: None)
    monkeypatch.setattr(fullscreen_module, "glGetUniformLocation", lambda _program, name: len(name))
    monkeypatch.setattr(fullscreen_module, "glViewport", lambda *_args: None)
    monkeypatch.setattr(fullscreen_module, "glClear", lambda *_args: None)
    monkeypatch.setattr(
        fullscreen_module,
        "glUniform1f",
        lambda *args: calls["uniform1f"].append(args),
    )
    monkeypatch.setattr(
        fullscreen_module,
        "glUniform2fv",
        lambda *args: calls["uniform2fv"].append(args),
    )
    monkeypatch.setattr(
        fullscreen_module,
        "glUniform3fv",
        lambda *args: calls["uniform3fv"].append(args),
    )
    monkeypatch.setattr(
        fullscreen_module,
        "glUniform4fv",
        lambda *args: calls["uniform4fv"].append(args),
    )
    monkeypatch.setattr(
        fullscreen_module,
        "glUniformMatrix4fv",
        lambda *args: calls["uniform_matrix4fv"].append(args),
    )
    monkeypatch.setattr(
        fullscreen_module,
        "glActiveTexture",
        lambda *args: calls["active_texture"].append(args),
    )
    monkeypatch.setattr(
        fullscreen_module,
        "glBindTexture",
        lambda *args: calls["bind_texture"].append(args),
    )
    monkeypatch.setattr(
        fullscreen_module,
        "glUniform1i",
        lambda *args: calls["uniform1i"].append(args),
    )
    monkeypatch.setattr(
        fullscreen_module,
        "glDrawArrays",
        lambda *args: calls["draw"].append(args),
    )
    return calls


class TestFullscreenShaderRuntime:
    """Keep the shared shader runtime narrow and predictable."""

    def test_initialize_compiles_program_and_binds_attribute(self, monkeypatch) -> None:
        calls = _install_compile_stubs(monkeypatch)
        runtime = FullscreenShaderRuntime()

        runtime.initialize(
            vertex_source="void main() {}",
            fragment_source="void main() {}",
            attribute_name="vPosition",
        )

        assert runtime.program == 101
        assert calls["attrib"] == [(101, 0, "vPosition")]

    def test_draw_applies_supported_uniform_shapes(self, monkeypatch) -> None:
        calls = _install_compile_stubs(monkeypatch)
        runtime = FullscreenShaderRuntime()
        runtime.initialize(fragment_source="void main() {}")

        matrix = np.identity(4, dtype=np.float32)
        runtime.draw(
            viewport_size=(64, 32),
            uniforms={
                "u_float": 1.5,
                "u_vec2": (1.0, 2.0),
                "u_vec3": (1.0, 2.0, 3.0),
                "u_vec4": (1.0, 2.0, 3.0, 4.0),
                "u_mat4": matrix,
                "u_texture": TextureUniform(texture_id=77, texture_unit=2),
            },
        )

        assert calls["uniform1f"][0] == (len("u_float"), 1.5)
        assert calls["uniform2fv"][0][0:2] == (len("u_vec2"), 1)
        assert calls["uniform3fv"][0][0:2] == (len("u_vec3"), 1)
        assert calls["uniform4fv"][0][0:2] == (len("u_vec4"), 1)
        matrix_call = calls["uniform_matrix4fv"][0]
        assert matrix_call[:3] == (len("u_mat4"), 1, False)
        np.testing.assert_array_equal(matrix_call[3], matrix)
        assert calls["active_texture"][0] == (fullscreen_module.GL_TEXTURE0 + 2,)
        assert calls["bind_texture"][0] == (fullscreen_module.GL_TEXTURE_2D, 77)
        assert calls["uniform1i"][0] == (len("u_texture"), 2)
        assert calls["draw"]

    def test_read_to_surface_flips_opengl_pixels_into_pygame_surface(
        self, monkeypatch
    ) -> None:
        window = _make_window(width=2, height=2)
        runtime = FullscreenShaderRuntime()

        def fake_read_pixels(_x, _y, _width, _height, _fmt, _kind, target) -> None:
            target[0, :, :] = (255, 0, 0, 255)
            target[1, :, :] = (0, 0, 255, 255)

        monkeypatch.setattr(fullscreen_module, "glReadPixels", fake_read_pixels)

        runtime.read_to_surface(window, size=(2, 2))

        assert window.screen.get_at((0, 0))[:3] == (0, 0, 255)
        assert window.screen.get_at((0, 1))[:3] == (255, 0, 0)

    def test_reset_clears_cached_runtime_state(self, monkeypatch) -> None:
        monkeypatch.setattr(fullscreen_module, "glDeleteProgram", lambda *_args: None)
        runtime = FullscreenShaderRuntime()
        runtime.program = 1
        runtime.uniform_locations["u_time"] = 2
        runtime.pixel_buffer = np.zeros((1, 1, 4), dtype=np.uint8)

        runtime.reset()

        assert runtime.program is None
        assert runtime.uniform_locations == {}
        assert runtime.pixel_buffer is None

    def test_reset_deletes_compiled_program(self, monkeypatch) -> None:
        deleted_programs: list[int] = []
        monkeypatch.setattr(fullscreen_module, "glDeleteProgram", deleted_programs.append)
        runtime = FullscreenShaderRuntime()
        runtime.program = 101

        runtime.reset()

        assert deleted_programs == [101]
