import os

TRUE_FLAG_VALUES = {"true", "1", "yes", "on"}


def _env_flag(env_var: str, *, default: bool = False) -> bool:
    """Return the boolean value of ``env_var`` respecting common true strings."""

    value = os.environ.get(env_var)
    if value is None:
        return default
    return value.strip().lower() in TRUE_FLAG_VALUES


def _env_int(env_var: str, *, default: int, minimum: int | None = None) -> int:
    """Return the integer value of ``env_var`` with optional bounds checking."""

    value = os.environ.get(env_var)
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{env_var} must be an integer") from exc
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{env_var} must be at least {minimum}")
    return parsed


def _env_optional_int(env_var: str, *, minimum: int | None = None) -> int | None:
    """Return the integer value of ``env_var`` or ``None`` when unset."""

    value = os.environ.get(env_var)
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(f"{env_var} must be an integer") from exc
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{env_var} must be at least {minimum}")
    return parsed


def _env_float(
    env_var: str,
    *,
    default: float,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    """Return the float value of ``env_var`` with optional bounds checking."""

    value = os.environ.get(env_var)
    if value is None:
        return default
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{env_var} must be a float") from exc
    if minimum is not None and parsed < minimum:
        raise ValueError(f"{env_var} must be at least {minimum}")
    if maximum is not None and parsed > maximum:
        raise ValueError(f"{env_var} must be at most {maximum}")
    return parsed
