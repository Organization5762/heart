from __future__ import annotations

import json
from pathlib import Path

import pygame

from heart.testing.state_similarity import (
    StateSimilarityAction,
    StateSimilarityScenario,
)
from heart.testing.state_similarity_review import (
    discover_state_similarity_scenarios,
    generate_state_similarity_review,
)
from heart.testing.state_similarity_review_cli import parse_args
from heart.testing.state_similarity_workflows import StateSimilarityTransition


class _WorkflowProbe:
    def __init__(
        self,
        scenario: StateSimilarityScenario,
        instances: list["_WorkflowProbe"],
    ) -> None:
        self.scenario = scenario
        self.scene_index = 0
        self.transition_fraction: float | None = None
        self.executed_actions: list[StateSimilarityAction] = []
        self.advance_deltas: list[float] = []
        self.was_cleaned_up = False
        instances.append(self)

    def execute_action(self, action: StateSimilarityAction) -> None:
        self.executed_actions.append(action)
        if action.type in {"navigate", "navigate-static"}:
            self.scene_index += 1
            self.transition_fraction = (
                0.0 if action.type == "navigate" else None
            )

    def project_state(self) -> object:
        return {
            "scene_index": self.scene_index,
            "unsafe": "<state & value>",
        }

    def render(self) -> pygame.Surface:
        surface = pygame.Surface((2, 1))
        color = (10, 20, 30) if self.scene_index == 0 else (40, 50, 60)
        surface.fill(color)
        return surface

    def advance_frame(self, delta_ms: float) -> None:
        self.advance_deltas.append(delta_ms)
        if self.transition_fraction is not None:
            self.transition_fraction = min(
                1.0,
                self.transition_fraction + delta_ms / 333.0,
            )

    def transition_progress(self) -> StateSimilarityTransition | None:
        if self.transition_fraction is None:
            return None
        return StateSimilarityTransition(
            fraction=self.transition_fraction,
            sliding=self.transition_fraction < 1.0,
        )

    def cleanup(self) -> None:
        self.was_cleaned_up = True


def test_review_embeds_escaped_checkpoints_and_isolates_transition_ticks(
    tmp_path: Path,
) -> None:
    scenario_path = tmp_path / "unsafe-scenario.json"
    scenario_path.write_text(
        json.dumps(
            {
                "name": "<script>unsafe scenario</script>",
                "kind": "review-probe",
                "initial": {"config": {"scene_index": 0}},
                "actions": [
                    {
                        "type": "navigate",
                        "config": {"label": "<b>next & scene</b>"},
                    }
                ],
                "expected": {
                    "state": {
                        "scene_index": 1,
                        "unsafe": "<state & value>",
                    },
                    "screen": {
                        "shape": [1, 2, 3],
                        "fill": [40, 50, 60],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    instances: list[_WorkflowProbe] = []

    result = generate_state_similarity_review(
        [scenario_path],
        output_dir=tmp_path / "review",
        transition_frames=2,
        workflow_builder=lambda scenario: _WorkflowProbe(scenario, instances),
    )

    assert result.index_path == tmp_path / "review" / "index.html"
    assert len(result.scenario_pages) == 1
    assert len(instances) == 3
    initial_replay, faithful, transition_replay = instances
    assert initial_replay.advance_deltas == []
    assert initial_replay.executed_actions == []
    assert faithful.advance_deltas == []
    assert len(faithful.executed_actions) == 1
    assert len(transition_replay.executed_actions) == 1
    assert len(transition_replay.advance_deltas) == 2
    assert initial_replay.was_cleaned_up
    assert faithful.was_cleaned_up
    assert transition_replay.was_cleaned_up

    page = result.scenario_pages[0].read_text(encoding="utf-8")
    assert page.count("data:image/png;base64,") == 5
    assert "image-rendering: pixelated" in page
    assert "After action 1 · scene transition" in page
    assert "Transition sample 2/2 after action 1" in page
    assert "&lt;script&gt;unsafe scenario&lt;/script&gt;" in page
    assert "&lt;b&gt;next &amp; scene&lt;/b&gt;" in page
    assert "&lt;state &amp; value&gt;" in page
    assert "<script>unsafe scenario</script>" not in page

    index = result.index_path.read_text(encoding="utf-8")
    assert result.scenario_pages[0].name in index
    assert "matches expected" in index
    assert "&lt;script&gt;unsafe scenario&lt;/script&gt;" in index


def test_nonanimated_scene_change_is_still_labeled_as_transition(
    tmp_path: Path,
) -> None:
    scenario_path = tmp_path / "static-scene-change.json"
    scenario_path.write_text(
        json.dumps(
            {
                "name": "static scene change",
                "kind": "review-probe",
                "initial": {"config": {"scene_index": 0}},
                "actions": [{"type": "navigate-static", "config": {}}],
                "expected": {
                    "state": {
                        "scene_index": 1,
                        "unsafe": "<state & value>",
                    },
                    "screen": {
                        "shape": [1, 2, 3],
                        "fill": [40, 50, 60],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    instances: list[_WorkflowProbe] = []

    result = generate_state_similarity_review(
        [scenario_path],
        output_dir=tmp_path / "review",
        transition_frames=3,
        workflow_builder=lambda scenario: _WorkflowProbe(scenario, instances),
    )

    page = result.scenario_pages[0].read_text(encoding="utf-8")
    assert "After action 1 · scene transition" in page
    assert "Transition sample" not in page
    assert len(instances) == 2
    assert all(instance.advance_deltas == [] for instance in instances)


def test_review_includes_scenario_user_story(tmp_path: Path) -> None:
    scenario_path = tmp_path / "keyboard-navigation.json"
    scenario_path.write_text(
        json.dumps(
            {
                "name": "keyboard right twice then activate",
                "kind": "review-probe",
                "initial": {"config": {"scene_index": 0}},
                "actions": [],
                "expected": {
                    "state": {
                        "scene_index": 0,
                        "unsafe": "<state & value>",
                    },
                    "screen": {
                        "shape": [1, 2, 3],
                        "fill": [10, 20, 30],
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    instances: list[_WorkflowProbe] = []

    result = generate_state_similarity_review(
        [scenario_path],
        output_dir=tmp_path / "review",
        transition_frames=0,
        workflow_builder=lambda scenario: _WorkflowProbe(scenario, instances),
    )

    page = result.scenario_pages[0].read_text(encoding="utf-8")
    assert (
        "A person uses keyboard navigation to move two modes to the right"
        in page
    )
    assert "committed state renders the expected nonuniform screen" in page


def test_scenario_discovery_accepts_files_and_directories_without_duplicates(
    tmp_path: Path,
) -> None:
    scenario_path = tmp_path / "scenario.json"
    scenario_path.write_text("{}", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("not a scenario", encoding="utf-8")

    discovered = discover_state_similarity_scenarios([scenario_path, tmp_path])

    assert discovered == (scenario_path,)


def test_review_cli_parses_output_scenario_directories_and_transition_bound(
    tmp_path: Path,
) -> None:
    scenario_path = tmp_path / "one.json"
    scenario_directory = tmp_path / "scenarios"
    output = tmp_path / "html"

    arguments = parse_args(
        [
            str(scenario_path),
            "--scenario-dir",
            str(scenario_directory),
            "--output",
            str(output),
            "--transition-frames",
            "3",
        ]
    )

    assert arguments.paths == (scenario_path, scenario_directory)
    assert arguments.output == output
    assert arguments.transition_frames == 3
