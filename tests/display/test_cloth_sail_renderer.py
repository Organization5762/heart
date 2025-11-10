import importlib
import sys
import types

import numpy as np
import pygame
import pytest

from heart.device import Rectangle
from heart.peripheral.core.manager import PeripheralManager


def _return_one(*_args, **_kwargs):
    return 1


def _return_bytes(*_args, **_kwargs):
    return b""


def _noop(*_args, **_kwargs):
    return None


def _install_fake_opengl(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    fake_gl = types.ModuleType("OpenGL.GL")
    fake_gl.GL_ARRAY_BUFFER = 0
    fake_gl.GL_COLOR_BUFFER_BIT = 0
    fake_gl.GL_COMPILE_STATUS = 1
    fake_gl.GL_CULL_FACE = 0
    fake_gl.GL_DEPTH_TEST = 0
    fake_gl.GL_FALSE = 0
    fake_gl.GL_FLOAT = 0
    fake_gl.GL_FRAGMENT_SHADER = 0
    fake_gl.GL_LINK_STATUS = 1
    fake_gl.GL_PACK_ALIGNMENT = 1
    fake_gl.GL_RGB = 0
    fake_gl.GL_STATIC_DRAW = 0
    fake_gl.GL_TRIANGLE_STRIP = 0
    fake_gl.GL_UNSIGNED_BYTE = 0
    fake_gl.GL_VERTEX_SHADER = 0

    fake_gl.glAttachShader = _noop
    fake_gl.glBindAttribLocation = _noop
    fake_gl.glBindBuffer = _noop
    fake_gl.glBufferData = _noop
    fake_gl.glClear = _noop
    fake_gl.glClearColor = _noop
    fake_gl.glCompileShader = _noop
    fake_gl.glCreateProgram = _return_one
    fake_gl.glCreateShader = _return_one
    fake_gl.glDeleteShader = _noop
    fake_gl.glDisable = _noop
    fake_gl.glDisableVertexAttribArray = _noop
    fake_gl.glDrawArrays = _noop
    fake_gl.glEnableVertexAttribArray = _noop
    fake_gl.glGenBuffers = _return_one
    fake_gl.glGetProgramInfoLog = _return_bytes
    fake_gl.glGetProgramiv = _return_one
    fake_gl.glGetShaderInfoLog = _return_bytes
    fake_gl.glGetShaderiv = _return_one
    fake_gl.glGetUniformLocation = _return_one
    fake_gl.glLinkProgram = _noop
    fake_gl.glPixelStorei = _noop
    fake_gl.glReadPixels = _noop
    fake_gl.glShaderSource = _noop
    fake_gl.glUniform1f = _noop
    fake_gl.glUniform2f = _noop
    fake_gl.glUseProgram = _noop
    fake_gl.glVertexAttribPointer = _noop
    fake_gl.glViewport = _noop

    fake_pkg = types.ModuleType("OpenGL")
    fake_pkg.GL = fake_gl

    monkeypatch.setitem(sys.modules, "OpenGL", fake_pkg)
    monkeypatch.setitem(sys.modules, "OpenGL.GL", fake_gl)

    return fake_gl


class TestClothSailRenderer:
    """Group cloth sail renderer tests so pixel transfer resilience stays high for crash investigations."""

    def test_process_passes_contiguous_frame_to_pygame(
        self, monkeypatch: pytest.MonkeyPatch, stub_clock_factory
    ) -> None:
        """Verify process hands pygame a contiguous RGB buffer to avoid SDL segfaults when OpenGL fallbacks engage."""

        _install_fake_opengl(monkeypatch)
        monkeypatch.delitem(
            sys.modules, "heart.display.renderers.cloth_sail", raising=False
        )
        cloth_module = importlib.import_module(
            "heart.display.renderers.cloth_sail"
        )
        ClothSailRenderer = cloth_module.ClothSailRenderer

        renderer = ClothSailRenderer()
        renderer._program = 1
        renderer._uniform_time = 2
        renderer._uniform_resolution = 3
        renderer._uniform_wind = 4
        renderer._vertex_buffer = 5

        window = pygame.Surface((4, 4), pygame.SRCALPHA)
        orientation = Rectangle.with_layout(1, 1)
        manager = PeripheralManager()
        clock = stub_clock_factory()

        def _noop(*_args, **_kwargs) -> None:
            return None

        monkeypatch.setattr(clock, "tick_busy_loop", _noop, raising=False)

        for name in (
            "glUseProgram",
            "glUniform1f",
            "glUniform2f",
            "glViewport",
            "glClearColor",
            "glClear",
            "glBindBuffer",
            "glEnableVertexAttribArray",
            "glVertexAttribPointer",
            "glDrawArrays",
            "glDisableVertexAttribArray",
        ):
            monkeypatch.setattr(cloth_module, name, _noop)

        def _fake_read_pixels(_x, _y, width, height, *_args) -> None:
            gradient = np.arange(width * height * 3, dtype=np.uint8).reshape(
                height, width, 3
            )
            renderer._pixel_buffer[...] = gradient

        monkeypatch.setattr(cloth_module, "glReadPixels", _fake_read_pixels)

        captured: dict[str, np.ndarray] = {}

        def _capture_blit_array(surface: pygame.Surface, array: np.ndarray) -> None:
            assert surface is window
            captured["frame"] = array

        monkeypatch.setattr(pygame.surfarray, "blit_array", _capture_blit_array)

        renderer.process(window, clock, manager, orientation)

        frame = captured["frame"]
        assert frame.flags["C_CONTIGUOUS"] is True
        assert frame.shape == (4, 4, 3)
