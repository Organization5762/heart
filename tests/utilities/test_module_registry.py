"""Validate module discovery ignores metadata stubs that cannot be imported."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

from heart.utilities.module_registry import discover_registry


class TestDiscoverRegistry:
    """Exercise registry discovery edge cases so local syncs stay robust across macOS and Raspberry Pi environments."""

    def test_ignores_apple_double_python_files(
        self,
        tmp_path: Path,
        monkeypatch,
    ) -> None:
        """Verify AppleDouble sidecar files are skipped so synced config directories do not fail to import on the Pi."""

        package_dir = tmp_path / "registry_pkg"
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (package_dir / "valid.py").write_text(
            "def configure() -> str:\n    return 'ok'\n",
            encoding="utf-8",
        )
        (package_dir / "._ghost.py").write_text(
            "raise RuntimeError('should not import')\n",
            encoding="utf-8",
        )

        monkeypatch.syspath_prepend(str(tmp_path))
        importlib.invalidate_caches()

        try:
            registry = discover_registry(package_dir, "registry_pkg")
        finally:
            for module_name in ["registry_pkg", "registry_pkg.valid", "registry_pkg._ghost"]:
                sys.modules.pop(module_name, None)

        assert list(registry) == ["valid"]
