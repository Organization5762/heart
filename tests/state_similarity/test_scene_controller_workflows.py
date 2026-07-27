from functools import partial
from pathlib import Path

import pytest

from heart.testing.state_similarity import (assert_rgb_similar,
                                            load_state_similarity_scenario,
                                            run_state_workflow)
from heart.testing.state_similarity_workflows import \
    build_state_similarity_workflow

SCENARIO_PATHS = tuple(
    sorted(Path(__file__).with_name("scenarios").glob("controller*.json"))
)


@pytest.mark.parametrize(
    "scenario_path",
    SCENARIO_PATHS,
    ids=lambda path: path.stem,
)
def test_scene_controller_workflow(scenario_path: Path) -> None:
    scenario = load_state_similarity_scenario(scenario_path)
    workflow = build_state_similarity_workflow(scenario)
    try:
        snapshot = run_state_workflow(
            (partial(workflow.execute_action, action) for action in scenario.actions),
            project_state=workflow.project_state,
            render=workflow.render,
        )
    finally:
        workflow.cleanup()

    assert snapshot.state == scenario.expected_state
    assert_rgb_similar(
        snapshot.rgb,
        scenario.expected_rgb,
        channel_tolerance=scenario.channel_tolerance,
        max_outlier_fraction=scenario.max_outlier_fraction,
    )
