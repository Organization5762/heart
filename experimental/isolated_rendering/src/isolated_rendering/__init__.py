"""Isolated rendering service for the heart LED matrix."""

from . import client as _client

MatrixClient = _client.MatrixClient
send_image = _client.send_image

del _client
