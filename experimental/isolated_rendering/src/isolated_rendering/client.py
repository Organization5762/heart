"""Client helpers for isolated rendering pipelines."""

from heart.device import isolated_render as _isolated_render

MatrixClient = _isolated_render.MatrixClient
send_image = _isolated_render.send_image

del _isolated_render
