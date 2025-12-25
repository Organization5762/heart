from ctypes import byref, c_int
from pathlib import Path

from OpenGL.GL import (GL_COMPILE_STATUS, GL_FRAGMENT_SHADER,
                       GL_INFO_LOG_LENGTH, GL_VERTEX_SHADER, glAttachShader,
                       glBindAttribLocation, glCompileShader, glCreateProgram,
                       glCreateShader, glDeleteShader, glGetShaderInfoLog,
                       glGetShaderiv, glGetUniformLocation, glLinkProgram,
                       glShaderSource, glUniform1f, glUniform3fv)

from heart.display.shaders.template import __file__ as template_location
from heart.display.shaders.util import _UNIFORMS, to_vec3
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class Shader:
    def __init__(self, obj=None):
        self.obj = obj
        self.keys = {}
        self.pending_uniforms = {}

    def set(self, key, val, lazy: bool = False):
        if key in _UNIFORMS:
            cur_val = _UNIFORMS[key]
            if type(val) is float and type(cur_val) is not float:
                val = to_vec3(val)
        _UNIFORMS[key] = val
        if key in self.keys:
            # todo: hack basically when tiling (i.e. across led screens) we
            #   the opengl programs lifetime is weird, so its safer to just
            #   queue the applications and apply them later
            if not lazy:
                key_id = self.keys[key]
                if type(val) is float:
                    glUniform1f(key_id, val)
                else:
                    glUniform3fv(key_id, 1, val)
            else:
                self.pending_uniforms[key] = val

    def get(self, key):
        if key in _UNIFORMS:
            return _UNIFORMS[key]
        return None

    def create(self):
        template_path = Path(template_location).parent
        with (template_path / "vert.glsl").open(encoding="utf-8") as f:
            vert_shader = f.read()

        with (template_path / "frag_gen.glsl").open(encoding="utf-8") as f:
            frag_shader = f.read()

        program = self.compile_program(vert_shader, frag_shader)
        for k in _UNIFORMS:
            self.keys[k] = glGetUniformLocation(program, "_" + k)

        # Return the program
        return program

    def compile_shader(self, source, shader_type):
        shader = glCreateShader(shader_type)
        glShaderSource(shader, source)
        glCompileShader(shader)

        status = c_int()
        glGetShaderiv(shader, GL_COMPILE_STATUS, byref(status))
        if not status.value:
            self.print_log(shader)
            glDeleteShader(shader)
            raise ValueError("Shader compilation failed")
        return shader

    def compile_program(self, vertex_source, fragment_source):
        vertex_shader = None
        fragment_shader = None
        program = glCreateProgram()

        if vertex_source:
            logger.info("Compiling Vertex Shader...")
            vertex_shader = self.compile_shader(vertex_source, GL_VERTEX_SHADER)
            glAttachShader(program, vertex_shader)
        if fragment_source:
            logger.info("Compiling Fragment Shader...")
            fragment_shader = self.compile_shader(fragment_source, GL_FRAGMENT_SHADER)
            glAttachShader(program, fragment_shader)

        glBindAttribLocation(program, 0, "vPosition")
        glLinkProgram(program)

        if vertex_shader:
            glDeleteShader(vertex_shader)
        if fragment_shader:
            glDeleteShader(fragment_shader)

        return program

    def print_log(self, shader):
        length = c_int()
        glGetShaderiv(shader, GL_INFO_LOG_LENGTH, byref(length))

        if length.value > 0:
            info_log = glGetShaderInfoLog(shader)
            if isinstance(info_log, bytes):
                info_log = info_log.decode("utf-8", errors="replace")
            logger.error("Shader compile log: %s", info_log)
