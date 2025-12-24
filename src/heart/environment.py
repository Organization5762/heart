"""Compatibility module for the runtime loop.

Prefer importing from :mod:`heart.runtime.game_loop` directly.
"""

from heart.runtime import game_loop as _game_loop

DeviceDisplayMode = _game_loop.DeviceDisplayMode
GameLoop = _game_loop.GameLoop
RendererVariant = _game_loop.RendererVariant
