import os

from heart.utilities.env.parsing import _env_flag, _env_int


class ColorConfiguration:
    @classmethod
    def hsv_cache_max_size(cls) -> int:
        return _env_int("HEART_HSV_CACHE_MAX_SIZE", default=4096, minimum=0)

    @classmethod
    def hsv_calibration_enabled(cls) -> bool:
        mode = os.environ.get("HEART_HSV_CALIBRATION_MODE")
        if mode is not None:
            normalized = mode.strip().lower()
            if normalized in {"off", "fast", "strict"}:
                return normalized != "off"
            raise ValueError(
                "HEART_HSV_CALIBRATION_MODE must be 'off', 'fast', or 'strict'"
            )
        return _env_flag("HEART_HSV_CALIBRATION", default=True)

    @classmethod
    def hsv_calibration_mode(cls) -> str:
        mode = os.environ.get("HEART_HSV_CALIBRATION_MODE")
        if mode is None:
            return "strict" if cls.hsv_calibration_enabled() else "off"
        normalized = mode.strip().lower()
        if normalized in {"off", "fast", "strict"}:
            return normalized
        raise ValueError(
            "HEART_HSV_CALIBRATION_MODE must be 'off', 'fast', or 'strict'"
        )
