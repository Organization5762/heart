"""Validate the combined totem-plus-Beats launcher so the single-command workflow stays reliable."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import typer

from heart.cli.commands.run_beats import (BEATS_WEBSOCKET_ENV_VAR,
                                          FORWARD_TO_BEATS_ENV_VAR,
                                          build_beats_env,
                                          build_beats_websocket_url,
                                          build_totem_run_command,
                                          ensure_beats_dependencies,
                                          resolve_beats_workspace)


class TestRunBeatsCommandBuilders:
    """Exercise command and environment builders so the launcher keeps the runtime and UI in sync."""

    def test_build_totem_run_command_includes_requested_flags(self) -> None:
        """Verify runtime flags are preserved so the combined launcher does not silently change scene startup behaviour."""

        command = build_totem_run_command(
            configuration="lib_2025",
            add_low_power_mode=False,
            x11_forward=True,
        )

        assert command == [
            "uv",
            "run",
            "totem",
            "run",
            "--configuration",
            "lib_2025",
            "--x11-forward",
            "--no-add-low-power-mode",
        ]

    def test_build_beats_env_sets_websocket_url(self) -> None:
        """Verify the Beats app receives a websocket URL so the UI can attach to the runtime stream immediately on boot."""

        websocket_url = build_beats_websocket_url()
        env = build_beats_env({"PATH": "/bin"}, websocket_url=websocket_url)

        assert env[BEATS_WEBSOCKET_ENV_VAR] == websocket_url
        assert env["PATH"] == "/bin"

    def test_resolve_beats_workspace_uses_repo_root_for_relative_paths(self) -> None:
        """Verify relative Beats paths resolve from the repository root so the launcher works from any shell location."""

        repo_root = Path("/tmp/heart")

        assert resolve_beats_workspace(repo_root, Path("experimental/beats")) == Path(
            "/tmp/heart/experimental/beats"
        )

    def test_runtime_env_flag_name_remains_stable(self) -> None:
        """Verify the runtime forwarding env var stays stable so the combined launcher continues selecting the streamed device path."""

        assert FORWARD_TO_BEATS_ENV_VAR == "FORWARD_TO_BEATS_APP"


class TestEnsureBeatsDependencies:
    """Cover Beats dependency bootstrap behaviour so the one-command launcher is usable in a fresh worktree."""

    def test_skips_install_when_node_modules_exists(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Verify bootstrap is skipped for installed workspaces so repeated launches avoid unnecessary npm churn."""

        beats_workspace = tmp_path / "beats"
        (beats_workspace / "node_modules").mkdir(parents=True)

        def _unexpected_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
            raise AssertionError("npm install should not run when node_modules exists")

        monkeypatch.setattr(subprocess, "run", _unexpected_run)

        ensure_beats_dependencies(beats_workspace)

    def test_installs_dependencies_when_node_modules_is_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Verify bootstrap runs npm install so first-time launcher use can start Beats without separate setup steps."""

        beats_workspace = tmp_path / "beats"
        beats_workspace.mkdir()
        commands: list[tuple[list[str], Path]] = []

        def _run(
            command: list[str], *, cwd: Path, check: bool
        ) -> subprocess.CompletedProcess[bytes]:
            commands.append((command, cwd))
            return subprocess.CompletedProcess(command, 0)

        monkeypatch.setattr(subprocess, "run", _run)

        ensure_beats_dependencies(beats_workspace)

        assert commands == [
            (["npm", "install", "--package-lock=false"], beats_workspace)
        ]

    def test_raises_exit_when_npm_install_fails(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Verify bootstrap fails loudly on npm errors so users do not end up debugging a half-started combined session."""

        beats_workspace = tmp_path / "beats"
        beats_workspace.mkdir()

        def _run(
            command: list[str], *, cwd: Path, check: bool
        ) -> subprocess.CompletedProcess[bytes]:
            return subprocess.CompletedProcess(command, 7)

        monkeypatch.setattr(subprocess, "run", _run)

        with pytest.raises(typer.Exit) as error:
            ensure_beats_dependencies(beats_workspace)

        assert error.value.exit_code == 7
