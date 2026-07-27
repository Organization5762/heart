from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import TypeAlias, cast, final

import numpy as np
import pygame
from numpy.typing import NDArray

JsonScalar: TypeAlias = None | bool | int | float | str
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

_SIMPLE_FIELD_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SCENARIO_REQUIRED_FIELDS = frozenset(
    {"name", "kind", "initial", "actions", "expected"}
)
_ACTION_FIELDS = frozenset({"type", "config"})
_EXPECTED_FIELDS = frozenset({"state", "screen"})


def load_state_similarity_scenario(path: str | Path) -> StateSimilarityScenario:
    """Load and strictly validate one machine-readable JSON scenario."""

    scenario_path = Path(path)
    try:
        with scenario_path.open(encoding="utf-8") as scenario_file:
            document = json.load(scenario_file)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"{scenario_path}: invalid JSON at line {error.lineno}, "
            f"column {error.colno}: {error.msg}"
        ) from error
    return parse_state_similarity_scenario(document, source=str(scenario_path))


def parse_state_similarity_scenario(
    document: object,
    *,
    source: str = "<scenario>",
) -> StateSimilarityScenario:
    """Validate a decoded JSON document and materialize its expected RGB."""

    _validate_json_value(document, path="$", source=source)
    scenario = _require_object(document, path="$", source=source)
    _validate_object_fields(
        scenario,
        required=_SCENARIO_REQUIRED_FIELDS,
        optional=frozenset(),
        path="$",
        source=source,
    )

    name = _require_non_empty_string(scenario["name"], path="$.name", source=source)
    kind = _require_non_empty_string(scenario["kind"], path="$.kind", source=source)
    initial = _parse_scenario_initial(scenario["initial"], source=source)
    actions = _parse_scenario_actions(scenario["actions"], source=source)
    expected = _require_object(
        scenario["expected"],
        path="$.expected",
        source=source,
    )
    _validate_object_fields(
        expected,
        required=_EXPECTED_FIELDS,
        optional=frozenset(),
        path="$.expected",
        source=source,
    )
    expected_state = _canonicalize_json_object(
        expected["state"],
        path="$.expected.state",
        source=source,
    )
    (
        expected_rgb,
        channel_tolerance,
        max_outlier_fraction,
    ) = _parse_expected_screen(expected["screen"], source=source)

    return StateSimilarityScenario(
        name=name,
        kind=kind,
        initial=initial,
        actions=actions,
        expected_state=expected_state,
        expected_rgb=expected_rgb,
        channel_tolerance=channel_tolerance,
        max_outlier_fraction=max_outlier_fraction,
    )


def run_state_workflow(
    commands: Iterable[Callable[[], object]],
    *,
    project_state: Callable[[], object],
    render: Callable[[], pygame.Surface],
) -> StateSimilaritySnapshot:
    """Run commands in order, then capture state and its rendered output."""

    for command in commands:
        command()

    state = canonicalize_state(project_state())
    rgb = capture_surface_rgb(render())
    return StateSimilaritySnapshot(state=state, rgb=rgb)


def canonicalize_state(value: object) -> JsonValue:
    """Convert an explicit state projection to deterministic JSON-compatible data."""

    return _canonicalize_state(value, path="$", active_ids=set())


def capture_surface_rgb(surface: pygame.Surface) -> NDArray[np.uint8]:
    """Copy a pygame surface into conventional ``(height, width, 3)`` RGB order."""

    if not isinstance(surface, pygame.Surface):
        raise TypeError(
            "render must return pygame.Surface, "
            f"got {type(surface).__qualname__}"
        )

    width_first_rgb = pygame.surfarray.array3d(surface)
    return np.ascontiguousarray(width_first_rgb.transpose(1, 0, 2), dtype=np.uint8)


def assert_rgb_similar(
    actual: NDArray[np.generic],
    expected: NDArray[np.generic],
    *,
    channel_tolerance: int = 0,
    max_outlier_fraction: float = 0.0,
) -> None:
    """Assert that only a bounded fraction of pixels exceed a channel tolerance."""

    channel_tolerance = _validate_channel_tolerance(channel_tolerance)
    max_outlier_fraction = _validate_max_outlier_fraction(max_outlier_fraction)

    actual_rgb = _validate_rgb_array(actual, label="actual")
    expected_rgb = _validate_rgb_array(expected, label="expected")
    if actual_rgb.shape != expected_rgb.shape:
        raise AssertionError(
            "RGB shape mismatch: "
            f"actual {actual_rgb.shape}, expected {expected_rgb.shape}"
        )

    channel_delta = np.abs(actual_rgb.astype(np.int16) - expected_rgb.astype(np.int16))
    pixel_delta = channel_delta.max(axis=2)
    outlier_mask = pixel_delta > channel_tolerance
    outlier_count = int(np.count_nonzero(outlier_mask))
    pixel_count = int(outlier_mask.size)
    outlier_fraction = outlier_count / pixel_count
    if outlier_fraction <= max_outlier_fraction:
        return

    worst_y, worst_x = np.unravel_index(int(pixel_delta.argmax()), pixel_delta.shape)
    worst_actual = tuple(int(channel) for channel in actual_rgb[worst_y, worst_x])
    worst_expected = tuple(int(channel) for channel in expected_rgb[worst_y, worst_x])
    worst_delta = tuple(int(channel) for channel in channel_delta[worst_y, worst_x])
    raise AssertionError(
        "RGB similarity failed: "
        f"{outlier_count}/{pixel_count} pixels "
        f"({outlier_fraction:.6%}) exceeded channel tolerance "
        f"{channel_tolerance}; allowed {max_outlier_fraction:.6%}. "
        f"Maximum channel delta {int(pixel_delta[worst_y, worst_x])} at "
        f"(y={worst_y}, x={worst_x}); actual={worst_actual}, "
        f"expected={worst_expected}, delta={worst_delta}"
    )


@final
@dataclass(frozen=True)
class StateSimilarityInitial:
    """Exactly one initial configuration or explicit initial state."""

    config: dict[str, JsonValue] | None = None
    state: dict[str, JsonValue] | None = None


@final
@dataclass(frozen=True)
class StateSimilarityAction:
    """One typed action and its JSON-compatible configuration."""

    type: str
    config: dict[str, JsonValue]


@final
@dataclass(frozen=True)
class StateSimilarityScenario:
    """A validated state and RGB workflow scenario loaded from JSON."""

    name: str
    kind: str
    initial: StateSimilarityInitial
    actions: tuple[StateSimilarityAction, ...]
    expected_state: dict[str, JsonValue]
    expected_rgb: NDArray[np.uint8]
    channel_tolerance: int
    max_outlier_fraction: float


@final
@dataclass(frozen=True)
class StateSimilaritySnapshot:
    """Canonical state and the RGB output rendered from that state."""

    state: JsonValue
    rgb: NDArray[np.uint8]


def _validate_json_value(value: object, *, path: str, source: str) -> None:
    if value is None or type(value) in (bool, int, str):
        return
    if type(value) is float:
        if not math.isfinite(cast(float, value)):
            raise _scenario_error(source, path, "number must be finite")
        return
    if type(value) is list:
        for index, item in enumerate(cast(list[object], value)):
            _validate_json_value(item, path=f"{path}[{index}]", source=source)
        return
    if type(value) is dict:
        for key, item in cast(dict[object, object], value).items():
            if type(key) is not str:
                raise _scenario_error(
                    source,
                    path,
                    f"object key must be a string, got {key!r}",
                )
            _validate_json_value(
                item,
                path=_field_path(path, cast(str, key)),
                source=source,
            )
        return
    raise _scenario_error(
        source,
        path,
        f"expected a JSON value, got {type(value).__qualname__}",
    )


def _parse_scenario_initial(
    value: object,
    *,
    source: str,
) -> StateSimilarityInitial:
    path = "$.initial"
    initial = _require_object(value, path=path, source=source)
    unknown = sorted(set(initial) - {"config", "state"})
    if unknown:
        raise _scenario_error(
            source,
            path,
            f"unknown fields: {', '.join(unknown)}",
        )
    if len(initial) != 1:
        raise _scenario_error(
            source,
            path,
            "expected exactly one initial field: config or state",
        )
    if "config" in initial:
        return StateSimilarityInitial(
            config=_canonicalize_json_object(
                initial["config"],
                path="$.initial.config",
                source=source,
            )
        )
    return StateSimilarityInitial(
        state=_canonicalize_json_object(
            initial["state"],
            path="$.initial.state",
            source=source,
        )
    )


def _parse_scenario_actions(
    value: object,
    *,
    source: str,
) -> tuple[StateSimilarityAction, ...]:
    if type(value) is not list:
        raise _scenario_error(source, "$.actions", "expected an array")

    actions: list[StateSimilarityAction] = []
    for index, action_value in enumerate(cast(list[object], value)):
        action_path = f"$.actions[{index}]"
        action = _require_object(
            action_value,
            path=action_path,
            source=source,
        )
        _validate_object_fields(
            action,
            required=_ACTION_FIELDS,
            optional=frozenset(),
            path=action_path,
            source=source,
        )
        action_type = _require_non_empty_string(
            action["type"],
            path=f"{action_path}.type",
            source=source,
        )
        action_config = _canonicalize_json_object(
            action["config"],
            path=f"{action_path}.config",
            source=source,
        )
        if action_type == "tick" and "count" in action_config:
            count = action_config["count"]
            if type(count) is not int or cast(int, count) <= 0:
                raise _scenario_error(
                    source,
                    f"{action_path}.config.count",
                    "expected a positive integer",
                )
        actions.append(
            StateSimilarityAction(
                type=action_type,
                config=action_config,
            )
        )
    return tuple(actions)


def _parse_expected_screen(
    value: object,
    *,
    source: str,
) -> tuple[NDArray[np.uint8], int, float]:
    rgb_path = "$.expected.screen"
    rgb = _require_object(value, path=rgb_path, source=source)
    _validate_object_fields(
        rgb,
        required=frozenset({"shape"}),
        optional=frozenset(
            {
                "fill",
                "pixels",
                "rows",
                "channel_tolerance",
                "max_outlier_fraction",
            }
        ),
        path=rgb_path,
        source=source,
    )
    encoding_fields = {"fill", "pixels", "rows"}.intersection(rgb)
    if len(encoding_fields) != 1:
        raise _scenario_error(
            source,
            rgb_path,
            "expected exactly one RGB encoding field: fill, pixels, or rows",
        )

    shape = _parse_rgb_shape(rgb["shape"], source=source)
    if "fill" in rgb:
        fill = rgb["fill"]
        if type(fill) is not list or len(cast(list[object], fill)) != 3:
            raise _scenario_error(
                source,
                f"{rgb_path}.fill",
                "expected exactly three RGB channel values",
            )
        candidate = np.asarray([[cast(list[object], fill)]])
        validated = _validate_scenario_rgb(
            candidate,
            path=f"{rgb_path}.fill",
            source=source,
        )
        expected_rgb = np.full(shape, validated[0, 0], dtype=np.uint8)
    elif "pixels" in rgb:
        try:
            candidate = np.asarray(rgb["pixels"])
        except (TypeError, ValueError) as error:
            raise _scenario_error(
                source,
                f"{rgb_path}.pixels",
                f"could not form an RGB array: {error}",
            ) from error
        validated = _validate_scenario_rgb(
            candidate,
            path=f"{rgb_path}.pixels",
            source=source,
        )
        if validated.shape != shape:
            raise _scenario_error(
                source,
                f"{rgb_path}.shape",
                f"declared {list(shape)} but pixels have shape "
                f"{list(validated.shape)}",
            )
        expected_rgb = np.ascontiguousarray(validated, dtype=np.uint8)
    else:
        try:
            candidate = np.asarray(rgb["rows"])
        except (TypeError, ValueError) as error:
            raise _scenario_error(
                source,
                f"{rgb_path}.rows",
                f"could not form an RGB row array: {error}",
            ) from error
        validated = _validate_scenario_rows(
            candidate,
            path=f"{rgb_path}.rows",
            source=source,
        )
        if validated.shape[0] != shape[0]:
            raise _scenario_error(
                source,
                f"{rgb_path}.shape",
                f"declared height {shape[0]} but rows have height "
                f"{validated.shape[0]}",
            )
        expected_rgb = np.ascontiguousarray(
            np.repeat(validated[:, np.newaxis, :], shape[1], axis=1),
            dtype=np.uint8,
        )

    channel_tolerance_value = rgb.get("channel_tolerance", 0)
    try:
        channel_tolerance = _validate_channel_tolerance(channel_tolerance_value)
    except ValueError as error:
        raise _scenario_error(
            source,
            f"{rgb_path}.channel_tolerance",
            str(error),
        ) from error
    max_outlier_fraction_value = rgb.get("max_outlier_fraction", 0.0)
    try:
        max_outlier_fraction = _validate_max_outlier_fraction(
            max_outlier_fraction_value
        )
    except ValueError as error:
        raise _scenario_error(
            source,
            f"{rgb_path}.max_outlier_fraction",
            str(error),
        ) from error
    return expected_rgb, channel_tolerance, max_outlier_fraction


def _parse_rgb_shape(value: object, *, source: str) -> tuple[int, int, int]:
    path = "$.expected.screen.shape"
    if type(value) is not list or len(cast(list[object], value)) != 3:
        raise _scenario_error(
            source,
            path,
            "expected [height, width, 3]",
        )
    shape_values = cast(list[object], value)
    if any(type(dimension) is not int for dimension in shape_values):
        raise _scenario_error(source, path, "dimensions must be integers")
    height, width, channels = cast(tuple[int, int, int], tuple(shape_values))
    if height <= 0 or width <= 0 or channels != 3:
        raise _scenario_error(
            source,
            path,
            "expected positive height and width with exactly 3 channels",
        )
    return height, width, channels


def _validate_scenario_rgb(
    value: NDArray[np.generic],
    *,
    path: str,
    source: str,
) -> NDArray[np.generic]:
    try:
        return _validate_rgb_array(value, label=path)
    except AssertionError as error:
        raise _scenario_error(source, path, str(error)) from error


def _validate_scenario_rows(
    value: NDArray[np.generic],
    *,
    path: str,
    source: str,
) -> NDArray[np.generic]:
    rows = np.asarray(value)
    if rows.ndim != 2 or rows.shape[1] != 3:
        raise _scenario_error(
            source,
            path,
            f"RGB rows must have shape (height, 3), got {rows.shape}",
        )
    return _validate_scenario_rgb(
        rows[:, np.newaxis, :],
        path=path,
        source=source,
    )[:, 0, :]


def _require_object(
    value: object,
    *,
    path: str,
    source: str,
) -> dict[str, object]:
    if type(value) is not dict:
        raise _scenario_error(source, path, "expected an object")
    return cast(dict[str, object], value)


def _canonicalize_json_object(
    value: object,
    *,
    path: str,
    source: str,
) -> dict[str, JsonValue]:
    json_object = _require_object(value, path=path, source=source)
    return cast(dict[str, JsonValue], canonicalize_state(json_object))


def _validate_object_fields(
    value: dict[str, object],
    *,
    required: frozenset[str],
    optional: frozenset[str],
    path: str,
    source: str,
) -> None:
    actual = set(value)
    missing = sorted(required - actual)
    if missing:
        raise _scenario_error(
            source,
            path,
            f"missing required fields: {', '.join(missing)}",
        )
    unknown = sorted(actual - required - optional)
    if unknown:
        raise _scenario_error(
            source,
            path,
            f"unknown fields: {', '.join(unknown)}",
        )


def _require_non_empty_string(value: object, *, path: str, source: str) -> str:
    if type(value) is not str or not cast(str, value).strip():
        raise _scenario_error(source, path, "expected a non-empty string")
    return cast(str, value)


def _scenario_error(source: str, path: str, message: str) -> ValueError:
    return ValueError(f"{source} {path}: {message}")


def _validate_channel_tolerance(value: object) -> int:
    if type(value) is not int or not 0 <= cast(int, value) <= 255:
        raise ValueError("must be an integer from 0 through 255")
    return cast(int, value)


def _validate_max_outlier_fraction(value: object) -> float:
    if (
        type(value) not in (int, float)
        or not math.isfinite(cast(int | float, value))
        or not 0.0 <= cast(int | float, value) <= 1.0
    ):
        raise ValueError("must be a number from 0.0 through 1.0")
    return float(cast(int | float, value))


def _canonicalize_state(
    value: object,
    *,
    path: str,
    active_ids: set[int],
) -> JsonValue:
    if value is None or isinstance(value, bool | str):
        return value
    if isinstance(value, Enum):
        return _canonicalize_state(value.value, path=path, active_ids=active_ids)
    if isinstance(value, np.generic):
        return _canonicalize_state(value.item(), path=path, active_ids=active_ids)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite float at {path}: {value!r}")
        return value
    if isinstance(value, np.ndarray):
        return _canonicalize_container(
            value,
            {
                "dtype": str(value.dtype),
                "shape": list(value.shape),
                "values": value.tolist(),
            },
            path=path,
            active_ids=active_ids,
        )
    if is_dataclass(value) and not isinstance(value, type):
        projected_fields = {
            field.name: getattr(value, field.name) for field in fields(value)
        }
        return _canonicalize_container(
            value,
            projected_fields,
            path=path,
            active_ids=active_ids,
        )
    if isinstance(value, Mapping):
        return _canonicalize_mapping(value, path=path, active_ids=active_ids)
    if isinstance(value, bytes | bytearray | memoryview):
        raise TypeError(
            f"unsupported state value at {path}: {type(value).__qualname__}"
        )
    if isinstance(value, Sequence):
        return _canonicalize_sequence(value, path=path, active_ids=active_ids)
    raise TypeError(f"unsupported state value at {path}: {type(value).__qualname__}")


def _canonicalize_container(
    owner: object,
    contents: object,
    *,
    path: str,
    active_ids: set[int],
) -> JsonValue:
    owner_id = id(owner)
    if owner_id in active_ids:
        raise ValueError(f"cyclic state value at {path}")
    active_ids.add(owner_id)
    try:
        return _canonicalize_state(contents, path=path, active_ids=active_ids)
    finally:
        active_ids.remove(owner_id)


def _canonicalize_mapping(
    value: Mapping[object, object],
    *,
    path: str,
    active_ids: set[int],
) -> dict[str, JsonValue]:
    value_id = id(value)
    if value_id in active_ids:
        raise ValueError(f"cyclic state value at {path}")

    active_ids.add(value_id)
    try:
        for key in value:
            if not isinstance(key, str):
                raise TypeError(
                    f"unsupported mapping key at {path}: expected str, "
                    f"got {type(key).__qualname__} {key!r}"
                )
        return {
            key: _canonicalize_state(
                value[key],
                path=_field_path(path, key),
                active_ids=active_ids,
            )
            for key in sorted(value)
        }
    finally:
        active_ids.remove(value_id)


def _canonicalize_sequence(
    value: Sequence[object],
    *,
    path: str,
    active_ids: set[int],
) -> list[JsonValue]:
    value_id = id(value)
    if value_id in active_ids:
        raise ValueError(f"cyclic state value at {path}")

    active_ids.add(value_id)
    try:
        return [
            _canonicalize_state(
                item,
                path=f"{path}[{index}]",
                active_ids=active_ids,
            )
            for index, item in enumerate(value)
        ]
    finally:
        active_ids.remove(value_id)


def _field_path(path: str, field_name: str) -> str:
    if _SIMPLE_FIELD_NAME.fullmatch(field_name):
        return f"{path}.{field_name}"
    escaped_name = field_name.replace("\\", "\\\\").replace('"', '\\"')
    return f'{path}["{escaped_name}"]'


def _validate_rgb_array(
    value: NDArray[np.generic],
    *,
    label: str,
) -> NDArray[np.generic]:
    rgb = np.asarray(value)
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise AssertionError(
            f"{label} RGB must have shape (height, width, 3), got {rgb.shape}"
        )
    if rgb.shape[0] == 0 or rgb.shape[1] == 0:
        raise AssertionError(f"{label} RGB must contain at least one pixel")
    if not np.issubdtype(rgb.dtype, np.number) or np.issubdtype(
        rgb.dtype, np.complexfloating
    ):
        raise AssertionError(
            f"{label} RGB must have a real numeric dtype, got {rgb.dtype}"
        )
    if not bool(np.all(np.isfinite(rgb))):
        raise AssertionError(f"{label} RGB contains non-finite values")
    if not bool(np.all((rgb >= 0) & (rgb <= 255))):
        raise AssertionError(f"{label} RGB values must be between 0 and 255")
    if not bool(np.all(rgb == np.floor(rgb))):
        raise AssertionError(f"{label} RGB values must be integers")
    return rgb
