import os

from heart.utilities.env.enums import DeviceLayoutMode
from heart.utilities.env.parsing import _env_int


class DeviceLayoutConfiguration:
    @classmethod
    def device_layout_mode(cls) -> DeviceLayoutMode:
        raw = os.environ.get("HEART_DEVICE_LAYOUT", "cube").strip().lower()
        try:
            return DeviceLayoutMode(raw)
        except ValueError as exc:
            raise ValueError(
                "HEART_DEVICE_LAYOUT must be 'cube' or 'rectangle'"
            ) from exc

    @classmethod
    def device_layout_columns(cls) -> int:
        return _env_int("HEART_LAYOUT_COLUMNS", default=1, minimum=1)

    @classmethod
    def device_layout_rows(cls) -> int:
        return _env_int("HEART_LAYOUT_ROWS", default=1, minimum=1)

    @classmethod
    def panel_rows(cls) -> int:
        return _env_int("HEART_PANEL_ROWS", default=64, minimum=1)

    @classmethod
    def panel_columns(cls) -> int:
        return _env_int("HEART_PANEL_COLUMNS", default=64, minimum=1)
