from heart.utilities.env.parsing import _env_int


class ReactivexConfiguration:
    @classmethod
    def reactivex_background_max_workers(cls) -> int:
        return _env_int("HEART_RX_BACKGROUND_MAX_WORKERS", default=4, minimum=1)

    @classmethod
    def reactivex_blocking_io_max_workers(cls) -> int:
        return _env_int("HEART_RX_BLOCKING_IO_MAX_WORKERS", default=2, minimum=1)

    @classmethod
    def reactivex_input_max_workers(cls) -> int:
        return _env_int("HEART_RX_INPUT_MAX_WORKERS", default=2, minimum=1)
