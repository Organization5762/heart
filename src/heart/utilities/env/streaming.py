import os

from heart.utilities.env.enums import BeatsStreamOverflowStrategy
from heart.utilities.env.parsing import _env_flag, _env_int, _env_optional_int


class StreamingConfiguration:
    @classmethod
    def beats_stream_queue_size(cls) -> int:
        return _env_int("HEART_BEATS_STREAM_QUEUE_SIZE", default=0, minimum=0)

    @classmethod
    def beats_stream_overflow_strategy(cls) -> BeatsStreamOverflowStrategy:
        strategy = os.environ.get(
            "HEART_BEATS_STREAM_OVERFLOW", "drop_newest"
        ).strip().lower()
        try:
            return BeatsStreamOverflowStrategy(strategy)
        except ValueError as exc:
            raise ValueError(
                "HEART_BEATS_STREAM_OVERFLOW must be 'drop_newest' or 'drop_oldest'"
            ) from exc

    @classmethod
    def beats_stream_json_sort_keys(cls) -> bool:
        return _env_flag("HEART_BEATS_STREAM_JSON_SORT_KEYS", default=True)

    @classmethod
    def beats_stream_json_indent(cls) -> int | None:
        raw = os.environ.get("HEART_BEATS_STREAM_JSON_INDENT")
        if raw is not None and raw.strip().lower() in {"none", "null"}:
            return None
        return _env_optional_int("HEART_BEATS_STREAM_JSON_INDENT", minimum=0)
