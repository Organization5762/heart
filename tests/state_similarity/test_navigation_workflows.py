from functools import partial
from pathlib import Path

import numpy as np
import pytest

from heart.testing.state_similarity import (StateSimilarityScenario,
                                            assert_rgb_similar,
                                            load_state_similarity_scenario,
                                            run_state_workflow)
from heart.testing.state_similarity_workflows import \
    build_state_similarity_workflow

SCENARIO_PATHS = tuple(
    sorted(Path(__file__).with_name("scenarios").glob("navigation*.json"))
)
SCENARIOS = tuple(load_state_similarity_scenario(path) for path in SCENARIO_PATHS)


@pytest.mark.parametrize(
    "scenario",
    SCENARIOS,
    ids=[scenario.name for scenario in SCENARIOS],
)
def test_navigation_workflow_matches_serialized_state_and_rgb(
    scenario: StateSimilarityScenario,
) -> None:
    workflow = build_state_similarity_workflow(scenario)
    try:
        result = run_state_workflow(
            (partial(workflow.execute_action, action) for action in scenario.actions),
            project_state=workflow.project_state,
            render=workflow.render,
        )
    finally:
        workflow.cleanup()

    assert result.state == scenario.expected_state
    assert_rgb_similar(
        result.rgb,
        scenario.expected_rgb,
        channel_tolerance=scenario.channel_tolerance,
        max_outlier_fraction=scenario.max_outlier_fraction,
    )


@pytest.mark.parametrize(
    "scenario",
    SCENARIOS,
    ids=[scenario.name for scenario in SCENARIOS],
)
def test_navigation_rgb_goldens_are_visually_discriminating(
    scenario: StateSimilarityScenario,
) -> None:
    unique_colors = np.unique(scenario.expected_rgb.reshape(-1, 3), axis=0)
    assert unique_colors.shape[0] >= 2


def test_game_modes_workflow_exposes_real_transition_progress() -> None:
    scenario = next(
        scenario
        for scenario in SCENARIOS
        if scenario.name == "keyboard right twice then activate"
    )
    workflow = build_state_similarity_workflow(scenario)
    try:
        workflow.execute_action(scenario.actions[0])
        workflow.render()

        initial_progress = workflow.transition_progress()
        assert initial_progress is not None
        assert initial_progress.fraction == 0.0
        assert initial_progress.sliding is True

        workflow.advance_frame(166.5)

        midpoint_progress = workflow.transition_progress()
        assert midpoint_progress is not None
        assert midpoint_progress.fraction == pytest.approx(0.5)
        assert midpoint_progress.sliding is True

        workflow.advance_frame(166.5)

        completed_progress = workflow.transition_progress()
        assert completed_progress is not None
        assert completed_progress.fraction == 1.0
        assert completed_progress.sliding is False
    finally:
        workflow.cleanup()
