"""Optional scene-management bridge backed by a PyO3 extension."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import ModuleType
from typing import Protocol, Sequence, cast

from heart.utilities.logging import get_logger
from heart.utilities.optional_imports import optional_import

NATIVE_SCENE_BRIDGE_MODULE = "heart_rgb_matrix_driver"

logger = get_logger(__name__)


class SceneManagerBackend(Protocol):
    """Resolve active scene indices for navigation flows."""

    def active_scene_index(self, current_button_value: int) -> int:
        """Return the active scene index for the current button value."""

    def register_scene(self, scene_name: str) -> None:
        """Register a scene name with the backend."""

    def reset_button_offset(self, current_button_value: int) -> None:
        """Anchor subsequent scene selection to ``current_button_value``."""


@dataclass
class PythonSceneManagerBridge:
    """Pure-Python fallback that mirrors the initial Rust bridge behaviour."""

    scene_names: list[str] = field(default_factory=list)
    offset_of_button_value: int | None = None

    def __init__(self, scene_names: Sequence[str]) -> None:
        self.scene_names = list(scene_names)
        self.offset_of_button_value = None

    def active_scene_index(self, current_button_value: int) -> int:
        """Return the wrapped scene index for ``current_button_value``."""

        if not self.scene_names:
            raise ValueError("Scene manager requires at least one registered scene")
        offset = self.offset_of_button_value or 0
        return (current_button_value - offset) % len(self.scene_names)

    def register_scene(self, scene_name: str) -> None:
        """Append a scene name to the fallback registry."""

        self.scene_names.append(scene_name)

    def reset_button_offset(self, current_button_value: int) -> None:
        """Store the current button value as the selection offset."""

        self.offset_of_button_value = current_button_value


def build_scene_manager_backend(
    scene_names: Sequence[str],
    *,
    prefer_native: bool = True,
) -> SceneManagerBackend:
    """Create a scene-manager backend, preferring the Rust bridge when available."""

    if prefer_native:
        native_module = _load_native_scene_bridge()
        if native_module is not None:
            bridge_type = getattr(native_module, "SceneManagerBridge", None)
            if bridge_type is not None:
                try:
                    return cast(SceneManagerBackend, bridge_type(list(scene_names)))
                except Exception:
                    logger.exception(
                        "Native scene bridge failed to initialize; using Python fallback."
                    )
            else:
                logger.warning(
                    "Native scene bridge module %s is missing SceneManagerBridge.",
                    NATIVE_SCENE_BRIDGE_MODULE,
                )
    return PythonSceneManagerBridge(scene_names)


def _load_native_scene_bridge() -> ModuleType | None:
    native_module = optional_import(NATIVE_SCENE_BRIDGE_MODULE, logger=logger)
    if native_module is None:
        logger.debug(
            "Native scene bridge %s is unavailable; using Python fallback.",
            NATIVE_SCENE_BRIDGE_MODULE,
        )
        return None
    return cast(ModuleType, native_module)
