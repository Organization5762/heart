"""Gamepad peripheral abstractions."""

from . import gamepad as _gamepad

Gamepad = _gamepad.Gamepad
GamepadIdentifier = _gamepad.GamepadIdentifier

del _gamepad
