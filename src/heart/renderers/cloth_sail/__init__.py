from heart.peripheral.core.providers import register_provider
from heart.renderers.cloth_sail.provider import \
    ClothSailStateProvider  # noqa: F401
from heart.renderers.cloth_sail.renderer import ClothSailRenderer  # noqa: F401
from heart.renderers.cloth_sail.renderer import glBindBuffer  # noqa: F401
from heart.renderers.cloth_sail.renderer import glClear  # noqa: F401
from heart.renderers.cloth_sail.renderer import glClearColor  # noqa: F401
from heart.renderers.cloth_sail.renderer import \
    glDisableVertexAttribArray  # noqa: F401
from heart.renderers.cloth_sail.renderer import glDrawArrays  # noqa: F401
from heart.renderers.cloth_sail.renderer import \
    glEnableVertexAttribArray  # noqa: F401
from heart.renderers.cloth_sail.renderer import glReadPixels  # noqa: F401
from heart.renderers.cloth_sail.renderer import glUniform1f  # noqa: F401
from heart.renderers.cloth_sail.renderer import glUniform2f  # noqa: F401
from heart.renderers.cloth_sail.renderer import glUseProgram  # noqa: F401
from heart.renderers.cloth_sail.renderer import \
    glVertexAttribPointer  # noqa: F401
from heart.renderers.cloth_sail.renderer import glViewport  # noqa: F401
from heart.renderers.cloth_sail.state import ClothSailState  # noqa: F401

register_provider(ClothSailStateProvider, ClothSailStateProvider)
