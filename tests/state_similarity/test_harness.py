import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np
import pygame
import pytest

from heart.testing import (
    StateSimilarityAction,
    StateSimilarityInitial,
    assert_rgb_similar,
    canonicalize_state,
    capture_surface_rgb,
    load_state_similarity_scenario,
    parse_state_similarity_scenario,
    run_state_workflow,
)


class _Mode(Enum):
    ACTIVE = "active"


@dataclass(frozen=True)
class _NestedState:
    mode: _Mode
    samples: np.ndarray
    count: np.int64


@dataclass(frozen=True)
class _ProgramState:
    nested: _NestedState
    labels: tuple[str, ...]


def _scenario_document() -> dict[str, object]:
    return {
        "name": "move right twice",
        "kind": "navigation",
        "initial": {"config": {"start": "home"}},
        "actions": [
            {"type": "navigate", "config": {"direction": "right"}},
            {"type": "tick", "config": {"count": 2}},
        ],
        "expected": {
            "state": {"screen": "settings"},
            "screen": {
                "fill": [10, 20, 30],
                "shape": [1, 2, 3],
                "channel_tolerance": 2,
                "max_outlier_fraction": 0.01,
            },
        },
    }


def test_load_state_similarity_scenario_materializes_typed_contract(
    tmp_path: Path,
) -> None:
    scenario_path = tmp_path / "navigation.json"
    scenario_path.write_text(json.dumps(_scenario_document()), encoding="utf-8")

    scenario = load_state_similarity_scenario(scenario_path)

    assert scenario.name == "move right twice"
    assert scenario.kind == "navigation"
    assert scenario.initial == StateSimilarityInitial(config={"start": "home"})
    assert scenario.actions == (
        StateSimilarityAction(
            type="navigate",
            config={"direction": "right"},
        ),
        StateSimilarityAction(
            type="tick",
            config={"count": 2},
        ),
    )
    assert scenario.expected_state == {"screen": "settings"}
    np.testing.assert_array_equal(
        scenario.expected_rgb,
        np.array([[[10, 20, 30], [10, 20, 30]]], dtype=np.uint8),
    )
    assert scenario.channel_tolerance == 2
    assert scenario.max_outlier_fraction == 0.01


def test_parse_state_similarity_scenario_accepts_full_pixel_rgb() -> None:
    document = _scenario_document()
    expected = document["expected"]
    assert isinstance(expected, dict)
    expected["screen"] = {
        "pixels": [[[1, 2, 3], [4, 5, 6]]],
        "shape": [1, 2, 3],
    }

    scenario = parse_state_similarity_scenario(document)

    np.testing.assert_array_equal(
        scenario.expected_rgb,
        np.array([[[1, 2, 3], [4, 5, 6]]], dtype=np.uint8),
    )
    assert scenario.channel_tolerance == 0
    assert scenario.max_outlier_fraction == 0.0


def test_parse_state_similarity_scenario_accepts_compact_rgb_rows() -> None:
    document = _scenario_document()
    expected = document["expected"]
    assert isinstance(expected, dict)
    expected["screen"] = {
        "rows": [[1, 2, 3], [4, 5, 6]],
        "shape": [2, 3, 3],
    }

    scenario = parse_state_similarity_scenario(document)

    np.testing.assert_array_equal(
        scenario.expected_rgb,
        np.array(
            [
                [[1, 2, 3], [1, 2, 3], [1, 2, 3]],
                [[4, 5, 6], [4, 5, 6], [4, 5, 6]],
            ],
            dtype=np.uint8,
        ),
    )


def test_parse_state_similarity_scenario_rejects_missing_and_unknown_fields() -> None:
    missing = _scenario_document()
    missing.pop("expected")
    with pytest.raises(
        ValueError,
        match=r"<scenario> \$: missing required fields: expected",
    ):
        parse_state_similarity_scenario(missing)

    unknown = _scenario_document()
    actions = unknown["actions"]
    assert isinstance(actions, list)
    actions[0]["repeat"] = 2
    with pytest.raises(
        ValueError,
        match=r"<scenario> \$\.actions\[0\]: unknown fields: repeat",
    ):
        parse_state_similarity_scenario(unknown)


def test_parse_state_similarity_scenario_requires_one_initial_source() -> None:
    document = _scenario_document()
    document["initial"] = {
        "config": {"start": "home"},
        "state": {"screen": "home"},
    }

    with pytest.raises(
        ValueError,
        match=(
            r"<scenario> \$\.initial: "
            r"expected exactly one initial field: config or state"
        ),
    ):
        parse_state_similarity_scenario(document)

    document["initial"] = {"state": {"screen": "home"}}
    scenario = parse_state_similarity_scenario(document)
    assert scenario.initial == StateSimilarityInitial(state={"screen": "home"})


def test_parse_state_similarity_scenario_validates_tick_count() -> None:
    document = _scenario_document()
    actions = document["actions"]
    assert isinstance(actions, list)
    actions[1]["config"] = {"count": 0}

    with pytest.raises(
        ValueError,
        match=(
            r"<scenario> \$\.actions\[1\]\.config\.count: "
            r"expected a positive integer"
        ),
    ):
        parse_state_similarity_scenario(document)


def test_parse_state_similarity_scenario_requires_strict_json_values() -> None:
    document = _scenario_document()
    initial = document["initial"]
    assert isinstance(initial, dict)
    config = initial["config"]
    assert isinstance(config, dict)
    config["sequence"] = ("left", "right")

    with pytest.raises(
        ValueError,
        match=(
            r"<scenario> \$\.initial\.config\.sequence: "
            r"expected a JSON value, got tuple"
        ),
    ):
        parse_state_similarity_scenario(document)


@pytest.mark.parametrize(
    ("expected_rgb", "error_path", "message"),
    [
        (
            {"fill": [0, 0, 256], "shape": [1, 1, 3]},
            r"\$\.expected\.screen\.fill",
            "RGB values must be between 0 and 255",
        ),
        (
            {"pixels": [[[0, 0, 0]]], "shape": [1, 2, 3]},
            r"\$\.expected\.screen\.shape",
            r"declared \[1, 2, 3\] but pixels have shape \[1, 1, 3\]",
        ),
        (
            {
                "fill": [0, 0, 0],
                "pixels": [[[0, 0, 0]]],
                "shape": [1, 1, 3],
            },
            r"\$\.expected\.screen",
            "expected exactly one RGB encoding field",
        ),
    ],
)
def test_parse_state_similarity_scenario_validates_rgb(
    expected_rgb: object,
    error_path: str,
    message: str,
) -> None:
    document = _scenario_document()
    expected = document["expected"]
    assert isinstance(expected, dict)
    expected["screen"] = expected_rgb

    with pytest.raises(ValueError, match=rf"{error_path}: .*{message}"):
        parse_state_similarity_scenario(document)


def test_parse_state_similarity_scenario_validates_similarity_bounds() -> None:
    document = _scenario_document()
    expected = document["expected"]
    assert isinstance(expected, dict)
    screen = expected["screen"]
    assert isinstance(screen, dict)
    screen["channel_tolerance"] = True

    with pytest.raises(
        ValueError,
        match=(
            r"<scenario> \$\.expected\.screen\.channel_tolerance: "
            r"must be an integer from 0 through 255"
        ),
    ):
        parse_state_similarity_scenario(document)


def test_load_state_similarity_scenario_reports_invalid_json_location(
    tmp_path: Path,
) -> None:
    scenario_path = tmp_path / "invalid.json"
    scenario_path.write_text('{"name":\n}', encoding="utf-8")

    with pytest.raises(
        ValueError,
        match=r"invalid\.json: invalid JSON at line 2, column 1",
    ):
        load_state_similarity_scenario(scenario_path)


def test_canonicalize_state_preserves_supported_values_as_strict_json() -> None:
    state = _ProgramState(
        nested=_NestedState(
            mode=_Mode.ACTIVE,
            samples=np.array([[1, 2], [3, 4]], dtype=np.uint8),
            count=np.int64(2),
        ),
        labels=("left", "right"),
    )

    canonical = canonicalize_state(state)

    assert canonical == {
        "labels": ["left", "right"],
        "nested": {
            "count": 2,
            "mode": "active",
            "samples": {
                "dtype": "uint8",
                "shape": [2, 2],
                "values": [[1, 2], [3, 4]],
            },
        },
    }
    assert json.loads(json.dumps(canonical, allow_nan=False)) == canonical


def test_canonicalize_state_preserves_empty_array_shape_and_dtype() -> None:
    canonical = canonicalize_state(np.empty((0, 3), dtype=np.float32))

    assert canonical == {
        "dtype": "float32",
        "shape": [0, 3],
        "values": [],
    }


def test_canonicalize_state_sorts_mapping_keys() -> None:
    canonical = canonicalize_state({"z": 1, "a": {"second": 2, "first": 1}})

    assert list(canonical) == ["a", "z"]
    assert list(canonical["a"]) == ["first", "second"]


def test_canonicalize_state_reports_unsupported_value_path() -> None:
    with pytest.raises(
        TypeError,
        match=r"unsupported state value at \$\.screens\[1\]\.controller: object",
    ):
        canonicalize_state(
            {"screens": [{"controller": "supported"}, {"controller": object()}]}
        )


def test_canonicalize_state_rejects_non_string_keys_and_cycles() -> None:
    with pytest.raises(TypeError, match=r"unsupported mapping key at \$\.inputs"):
        canonicalize_state({"inputs": {1: "south"}})

    cyclic: list[object] = []
    cyclic.append(cyclic)
    with pytest.raises(ValueError, match=r"cyclic state value at \$\[0\]"):
        canonicalize_state(cyclic)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), np.float32("-inf")])
def test_canonicalize_state_rejects_non_finite_numbers(value: object) -> None:
    with pytest.raises(ValueError, match=r"non-finite float at \$\.sensor"):
        canonicalize_state({"sensor": value})


def test_run_state_workflow_orders_commands_then_captures_state_and_rgb() -> None:
    events: list[str] = []
    position = {"x": 0}

    def move_right() -> None:
        events.append("right")
        position["x"] += 1

    def project_state() -> object:
        events.append("project")
        return {"position": position}

    def render() -> pygame.Surface:
        events.append("render")
        surface = pygame.Surface((2, 1))
        surface.set_at((0, 0), (10, 20, 30))
        surface.set_at((1, 0), (40, 50, 60))
        return surface

    snapshot = run_state_workflow(
        [move_right, move_right],
        project_state=project_state,
        render=render,
    )

    assert events == ["right", "right", "project", "render"]
    assert snapshot.state == {"position": {"x": 2}}
    np.testing.assert_array_equal(
        snapshot.rgb,
        np.array([[[10, 20, 30], [40, 50, 60]]], dtype=np.uint8),
    )
    assert snapshot.rgb.flags.c_contiguous


def test_capture_surface_rgb_uses_height_width_channel_order() -> None:
    surface = pygame.Surface((2, 3))
    surface.set_at((1, 2), (7, 8, 9))

    rgb = capture_surface_rgb(surface)

    assert rgb.shape == (3, 2, 3)
    assert tuple(rgb[2, 1]) == (7, 8, 9)


def test_assert_rgb_similar_applies_channel_and_outlier_bounds() -> None:
    expected = np.zeros((2, 2, 3), dtype=np.uint8)
    actual = expected.copy()
    actual[0, 0] = (2, 2, 2)
    actual[1, 1] = (3, 0, 0)

    assert_rgb_similar(
        actual,
        expected,
        channel_tolerance=2,
        max_outlier_fraction=0.25,
    )


def test_assert_rgb_similar_reports_actionable_pixel_diagnostics() -> None:
    expected = np.zeros((1, 2, 3), dtype=np.uint8)
    actual = expected.copy()
    actual[0, 1] = (3, 5, 4)

    with pytest.raises(AssertionError) as failure:
        assert_rgb_similar(actual, expected, channel_tolerance=2)

    message = str(failure.value)
    assert "1/2 pixels (50.000000%)" in message
    assert "Maximum channel delta 5 at (y=0, x=1)" in message
    assert "actual=(3, 5, 4), expected=(0, 0, 0), delta=(3, 5, 4)" in message


def test_assert_rgb_similar_reports_shape_mismatch() -> None:
    with pytest.raises(
        AssertionError,
        match=r"RGB shape mismatch: actual \(1, 2, 3\), expected \(2, 1, 3\)",
    ):
        assert_rgb_similar(
            np.zeros((1, 2, 3), dtype=np.uint8),
            np.zeros((2, 1, 3), dtype=np.uint8),
        )
