"""Validate renderer provider observable signatures used by StatefulBaseRenderer."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RENDERERS_ROOT = REPO_ROOT / "src/heart/renderers"
EXCLUDED_PROVIDER_CLASSES = {"FractalSceneProvider"}


def _provider_observable_sources() -> list[tuple[Path, str]]:
    providers: list[tuple[Path, str]] = []
    for source_path in RENDERERS_ROOT.rglob("*.py"):
        module = ast.parse(source_path.read_text(encoding="utf-8"))
        for node in module.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if not node.name.endswith("Provider"):
                continue
            if node.name in EXCLUDED_PROVIDER_CLASSES:
                continue
            if any(
                isinstance(class_node, ast.FunctionDef)
                and class_node.name == "observable"
                for class_node in node.body
            ):
                providers.append((source_path, node.name))
    return sorted(providers)


PROVIDER_SOURCES = tuple(_provider_observable_sources())


def _observable_accepts_renderer_manager(
    source_path: Path, class_name: str
) -> bool:
    module = ast.parse(source_path.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for class_node in node.body:
                if isinstance(class_node, ast.FunctionDef) and class_node.name == "observable":
                    positional_args = class_node.args.posonlyargs + class_node.args.args
                    return len(positional_args) >= 2 or class_node.args.vararg is not None
    raise AssertionError(f"Could not find observable() on {class_name} in {source_path}")


class TestRendererProviderObservableSignatures:
    """Ensure renderer providers match StatefulBaseRenderer's calling convention so scene initialization stays consistent."""

    @pytest.mark.parametrize(("source_path", "class_name"), PROVIDER_SOURCES)
    def test_observable_accepts_renderer_peripheral_manager(
        self, source_path: Path, class_name: str
    ) -> None:
        """Verify renderer provider observables accept the renderer-supplied peripheral manager so container-driven scenes do not fail at runtime."""
        assert _observable_accepts_renderer_manager(source_path, class_name)
