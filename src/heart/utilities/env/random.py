from heart.utilities.env.parsing import _env_optional_int


class RandomConfiguration:
    @classmethod
    def random_seed(cls) -> int | None:
        return _env_optional_int("HEART_RANDOM_SEED", minimum=0)
