from __future__ import annotations

import base64
import html
import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path
from typing import final

import numpy as np
from numpy.typing import NDArray
from PIL import Image

from heart.renderers.slide_transition.provider import DEFAULT_SLIDE_DURATION_MS
from heart.testing.state_similarity import (JsonValue, StateSimilarityAction,
                                            StateSimilarityScenario,
                                            assert_rgb_similar,
                                            canonicalize_state,
                                            capture_surface_rgb,
                                            load_state_similarity_scenario)
from heart.testing.state_similarity_workflows import (
    StateSimilarityTransition, StateSimilarityWorkflow,
    build_state_similarity_workflow)

DEFAULT_REVIEW_OUTPUT = Path("tmp/state-similarity-review")
DEFAULT_TRANSITION_FRAMES = 5

_SCENE_IDENTITY_KEYS = (
    "active_scene_index",
    "current_index",
    "scene_index",
    "current_entry",
    "active_scene_name",
)
_SLUG_CHARACTERS = re.compile(r"[^a-z0-9]+")
_SCENARIO_USER_STORIES = {
    "keyboard right twice then activate":
        "A person uses keyboard navigation to move two modes to the right and "
        "commit the highlighted mode. The test proves that edge-triggered "
        "keyboard input selects the intended program and that the committed "
        "state renders the expected nonuniform screen.",
    "gamepad right and south in one frame":
        "A controller sends D-pad right and confirm in the same sampled input "
        "frame. The test proves Heart handles the combined navigation event "
        "deterministically instead of dropping either the move or the commit.",
    "multi scene activate advances one scene":
        "A mode with multiple internal scenes receives an activation command "
        "from the shared navigation bus. The test proves the scene controller "
        "advances exactly one scene and renders that scene's visible output.",
    "controller tixyland":
        "A player changes Tixyland parameters with controller buttons and "
        "triggers over several frame ticks. The test proves renderer-local IO "
        "updates semantic state and produces a stable representative RGB frame.",
    "controller water cube":
        "A sensor update and controller input arrive while Water Cube advances "
        "physics ticks. The test proves external acceleration, trigger input, "
        "and frame timing converge into the expected state and visible water "
        "output.",
}
_PAGE_STYLE = """
:root {
  color-scheme: dark;
  font-family: ui-sans-serif, system-ui, sans-serif;
  background: #111318;
  color: #edf0f7;
}
body { margin: 0 auto; max-width: 1200px; padding: 2rem; }
a { color: #8fc7ff; }
.summary, .checkpoint {
  background: #1a1e27;
  border: 1px solid #303746;
  border-radius: 12px;
  margin: 1rem 0;
  padding: 1rem;
}
.user-story {
  border-left: 3px solid #8fc7ff;
  color: #d6deeb;
  line-height: 1.55;
  margin: 1rem 0;
  padding-left: 1rem;
}
.checkpoint.scene-transition { border-color: #d4a72c; }
.status-pass { color: #57d38c; }
.status-diff { color: #ff7b72; }
.frame {
  background: #07080b;
  border-radius: 8px;
  overflow: auto;
  padding: 1rem;
}
.frame img {
  display: block;
  height: auto;
  image-rendering: pixelated;
  image-rendering: crisp-edges;
  max-width: none;
  min-width: min(100%, 768px);
  width: 768px;
}
.data-grid {
  display: grid;
  gap: 1rem;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
}
pre {
  background: #0d0f14;
  border-radius: 8px;
  max-height: 36rem;
  overflow: auto;
  padding: 1rem;
  white-space: pre-wrap;
  word-break: break-word;
}
code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
small { color: #aab2c0; }
"""


@final
@dataclass(frozen=True)
class StateSimilarityReviewCheckpoint:
    """One faithful or isolated transition checkpoint rendered for review."""

    label: str
    kind: str
    state: JsonValue
    rgb: NDArray[np.uint8]
    action: JsonValue | None = None
    transition_fraction: float | None = None


@final
@dataclass(frozen=True)
class StateSimilarityReviewResult:
    """Generated static review artifacts."""

    index_path: Path
    scenario_pages: tuple[Path, ...]


WorkflowBuilder = Callable[[StateSimilarityScenario], StateSimilarityWorkflow]


def generate_state_similarity_review(
    scenario_paths: Iterable[str | Path],
    *,
    output_dir: str | Path = DEFAULT_REVIEW_OUTPUT,
    transition_frames: int = DEFAULT_TRANSITION_FRAMES,
    workflow_builder: WorkflowBuilder = build_state_similarity_workflow,
) -> StateSimilarityReviewResult:
    """Replay scenarios and write a self-contained static HTML review."""

    if isinstance(transition_frames, bool) or not isinstance(transition_frames, int):
        raise TypeError("transition_frames must be an integer")
    if transition_frames < 0:
        raise ValueError("transition_frames must be non-negative")

    resolved_paths = discover_state_similarity_scenarios(scenario_paths)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    pages: list[Path] = []
    summaries: list[tuple[str, str, bool]] = []
    used_names: set[str] = set()
    for scenario_path in resolved_paths:
        scenario = load_state_similarity_scenario(scenario_path)
        checkpoints = _replay_scenario(
            scenario,
            transition_frames=transition_frames,
            workflow_builder=workflow_builder,
        )
        page_name = _unique_page_name(scenario_path.stem, used_names)
        page_path = target / page_name
        faithful_final = next(
            checkpoint
            for checkpoint in reversed(checkpoints)
            if checkpoint.kind != "transition-sample"
        )
        matches_expected = _matches_expected(faithful_final, scenario)
        page_path.write_text(
            _scenario_page(
                scenario,
                source=scenario_path,
                checkpoints=checkpoints,
                matches_expected=matches_expected,
            ),
            encoding="utf-8",
        )
        pages.append(page_path)
        summaries.append((scenario.name, page_name, matches_expected))

    index_path = target / "index.html"
    index_path.write_text(_index_page(summaries), encoding="utf-8")
    return StateSimilarityReviewResult(
        index_path=index_path,
        scenario_pages=tuple(pages),
    )


def discover_state_similarity_scenarios(
    paths: Iterable[str | Path],
) -> tuple[Path, ...]:
    """Resolve JSON files from an explicit set of scenario files and directories."""

    discovered: list[Path] = []
    seen: set[Path] = set()
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            candidates = sorted(path.glob("*.json"))
        elif path.is_file():
            candidates = [path]
        else:
            raise FileNotFoundError(f"Scenario path does not exist: {path}")
        for candidate in candidates:
            if candidate.suffix.lower() != ".json":
                continue
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            discovered.append(candidate)
    if not discovered:
        raise ValueError("No JSON state-similarity scenarios were found")
    return tuple(discovered)


def _replay_scenario(
    scenario: StateSimilarityScenario,
    *,
    transition_frames: int,
    workflow_builder: WorkflowBuilder,
) -> tuple[StateSimilarityReviewCheckpoint, ...]:
    checkpoints: list[StateSimilarityReviewCheckpoint] = []
    initial, _ = _capture_faithful_prefix(
        scenario,
        action_count=0,
        label="Initial state",
        kind="initial",
        workflow_builder=workflow_builder,
    )
    checkpoints.append(initial)
    previous_identity = _scene_identity(initial.state)
    for action_index, action in enumerate(scenario.actions):
        checkpoint, transition = _capture_faithful_prefix(
            scenario,
            action_count=action_index + 1,
            label=f"After action {action_index + 1}",
            kind="action",
            action=_action_json(action),
            workflow_builder=workflow_builder,
        )
        current_identity = _scene_identity(checkpoint.state)
        is_scene_transition = (
            previous_identity is not None
            and current_identity is not None
            and previous_identity != current_identity
        )
        if is_scene_transition:
            checkpoint = replace(
                checkpoint,
                label=f"After action {action_index + 1} · scene transition",
                kind="scene-transition",
            )
        checkpoints.append(checkpoint)
        if (
            is_scene_transition
            and transition is not None
            and transition.sliding
            and transition_frames > 0
        ):
            checkpoints.extend(
                _sample_transition(
                    scenario,
                    action_index=action_index,
                    frame_count=transition_frames,
                    workflow_builder=workflow_builder,
                )
            )
        previous_identity = current_identity
    return tuple(checkpoints)


def _capture_faithful_prefix(
    scenario: StateSimilarityScenario,
    *,
    action_count: int,
    label: str,
    kind: str,
    workflow_builder: WorkflowBuilder,
    action: JsonValue | None = None,
) -> tuple[StateSimilarityReviewCheckpoint, StateSimilarityTransition | None]:
    """Capture one prefix without letting review rendering affect later prefixes."""

    workflow = workflow_builder(scenario)
    try:
        for prefix_action in scenario.actions[:action_count]:
            workflow.execute_action(prefix_action)
        return _capture_checkpoint(
            workflow,
            label=label,
            kind=kind,
            action=action,
        )
    finally:
        workflow.cleanup()


def _sample_transition(
    scenario: StateSimilarityScenario,
    *,
    action_index: int,
    frame_count: int,
    workflow_builder: WorkflowBuilder,
) -> tuple[StateSimilarityReviewCheckpoint, ...]:
    """Sample injected ticks on an isolated replay of the scenario prefix."""

    workflow = workflow_builder(scenario)
    samples: list[StateSimilarityReviewCheckpoint] = []
    try:
        for prefix_action in scenario.actions[: action_index + 1]:
            workflow.execute_action(prefix_action)
        _capture_checkpoint(workflow, label="Replay checkpoint", kind="replay")

        delta_ms = DEFAULT_SLIDE_DURATION_MS / (frame_count + 1)
        for sample_index in range(frame_count):
            transition = workflow.transition_progress()
            if transition is None or not transition.sliding:
                break
            workflow.advance_frame(delta_ms)
            checkpoint, sampled_transition = _capture_checkpoint(
                workflow,
                label=(
                    f"Transition sample {sample_index + 1}/{frame_count} "
                    f"after action {action_index + 1}"
                ),
                kind="transition-sample",
                action={
                    "type": "transition-sample",
                    "config": {
                        "source_action_index": action_index,
                        "sample_index": sample_index,
                        "delta_ms": delta_ms,
                    },
                },
            )
            samples.append(
                replace(
                    checkpoint,
                    transition_fraction=(
                        sampled_transition.fraction
                        if sampled_transition is not None
                        else None
                    ),
                )
            )
    finally:
        workflow.cleanup()
    return tuple(samples)


def _capture_checkpoint(
    workflow: StateSimilarityWorkflow,
    *,
    label: str,
    kind: str,
    action: JsonValue | None = None,
) -> tuple[StateSimilarityReviewCheckpoint, StateSimilarityTransition | None]:
    state = canonicalize_state(workflow.project_state())
    rgb = capture_surface_rgb(workflow.render())
    transition = workflow.transition_progress()
    return (
        StateSimilarityReviewCheckpoint(
            label=label,
            kind=kind,
            state=state,
            rgb=rgb,
            action=action,
            transition_fraction=(
                transition.fraction if transition is not None else None
            ),
        ),
        transition,
    )


def _scene_identity(state: JsonValue) -> tuple[str, JsonValue] | None:
    if isinstance(state, dict):
        for key in _SCENE_IDENTITY_KEYS:
            if key in state:
                return (key, state[key])
        for key, value in state.items():
            nested = _scene_identity(value)
            if nested is not None:
                return (f"{key}.{nested[0]}", nested[1])
    if isinstance(state, list):
        for index, value in enumerate(state):
            nested = _scene_identity(value)
            if nested is not None:
                return (f"[{index}].{nested[0]}", nested[1])
    return None


def _action_json(action: StateSimilarityAction) -> dict[str, JsonValue]:
    return {
        "type": action.type,
        "config": action.config,
    }


def _matches_expected(
    checkpoint: StateSimilarityReviewCheckpoint,
    scenario: StateSimilarityScenario,
) -> bool:
    if checkpoint.state != scenario.expected_state:
        return False
    try:
        assert_rgb_similar(
            checkpoint.rgb,
            scenario.expected_rgb,
            channel_tolerance=scenario.channel_tolerance,
            max_outlier_fraction=scenario.max_outlier_fraction,
        )
    except AssertionError:
        return False
    return True


def _scenario_page(
    scenario: StateSimilarityScenario,
    *,
    source: Path,
    checkpoints: tuple[StateSimilarityReviewCheckpoint, ...],
    matches_expected: bool,
) -> str:
    status_class = "status-pass" if matches_expected else "status-diff"
    status_text = "Matches expected final state and screen" if matches_expected else (
        "Final output differs from expected"
    )
    user_story = _SCENARIO_USER_STORIES.get(scenario.name)
    user_story_html = (
        "" if user_story is None else f'<p class="user-story">{_escape(user_story)}</p>'
    )
    checkpoint_html = "\n".join(_checkpoint_html(item) for item in checkpoints)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_escape(scenario.name)} · State similarity review</title>
<style>{_PAGE_STYLE}</style>
</head>
<body>
<p><a href="index.html">← All scenarios</a></p>
<h1>{_escape(scenario.name)}</h1>
<section class="summary">
  <p class="{status_class}"><strong>{status_text}</strong></p>
  {user_story_html}
  <p><small>Kind: {_escape(scenario.kind)} · Source: {_escape(str(source))}</small></p>
  <p>{len(checkpoints)} checkpoints, including isolated transition samples.</p>
</section>
{checkpoint_html}
<section class="checkpoint expected">
  <h2>Expected final output</h2>
  <div class="frame"><img alt="Expected final screen" src="{_png_data_uri(scenario.expected_rgb)}"></div>
  <h3>Expected state</h3>
  <pre><code>{_json_html(scenario.expected_state)}</code></pre>
</section>
</body>
</html>
"""


def _checkpoint_html(checkpoint: StateSimilarityReviewCheckpoint) -> str:
    action = (
        "<p><small>No action — initial program state.</small></p>"
        if checkpoint.action is None
        else f"<h3>Action</h3><pre><code>{_json_html(checkpoint.action)}</code></pre>"
    )
    fraction = (
        ""
        if checkpoint.transition_fraction is None
        else f"<p><small>Transition fraction: {checkpoint.transition_fraction:.4f}</small></p>"
    )
    return f"""<section class="checkpoint {_escape(checkpoint.kind)}">
  <h2>{_escape(checkpoint.label)}</h2>
  {fraction}
  <div class="frame"><img alt="{_escape(checkpoint.label)} screen" src="{_png_data_uri(checkpoint.rgb)}"></div>
  <div class="data-grid">
    <div>{action}</div>
    <div><h3>State</h3><pre><code>{_json_html(checkpoint.state)}</code></pre></div>
  </div>
</section>"""


def _index_page(summaries: list[tuple[str, str, bool]]) -> str:
    items = "\n".join(
        (
            f'<li><a href="{_escape(page_name)}">{_escape(name)}</a> '
            f'<span class="{"status-pass" if passed else "status-diff"}">'
            f'{"matches expected" if passed else "differs"}</span></li>'
        )
        for name, page_name, passed in summaries
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>State similarity review</title>
<style>{_PAGE_STYLE}</style>
</head>
<body>
<h1>State similarity review</h1>
<p>Static replay artifacts for {len(summaries)} scenarios.</p>
<ul>{items}</ul>
</body>
</html>
"""


def _png_data_uri(rgb: NDArray[np.uint8]) -> str:
    output = BytesIO()
    Image.fromarray(rgb, mode="RGB").save(output, format="PNG")
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _json_html(value: JsonValue) -> str:
    return _escape(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def _unique_page_name(stem: str, used_names: set[str]) -> str:
    slug = _SLUG_CHARACTERS.sub("-", stem.lower()).strip("-") or "scenario"
    candidate = f"{slug}.html"
    suffix = 2
    while candidate in used_names:
        candidate = f"{slug}-{suffix}.html"
        suffix += 1
    used_names.add(candidate)
    return candidate
