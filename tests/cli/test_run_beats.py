"""Validate the combined totem-plus-Beats launcher so the single-command workflow stays reliable."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from heart import loop
from heart.cli.commands import run as run_module
from heart.cli.commands.run_beats import (BEATS_WEBSOCKET_ENV_VAR,
                                          FORWARD_TO_BEATS_ENV_VAR,
                                          build_beats_env,
                                          build_beats_websocket_url,
                                          build_totem_run_command,
                                          ensure_beats_dependencies,
                                          resolve_beats_workspace)

runner = CliRunner()


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


class TestRunCommandWithBeats:
    """Validate the opt-in Beats CLI path so default runtime startup stays independent from the UI bundle."""

    def test_run_command_dispatches_to_beats_only_when_requested(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify `--with-beats` delegates into the Beats launcher so the UI starts only for explicitly requested sessions."""

        recorded_call: dict[str, object] = {}

        def _fake_run_beats_command(
            *,
            configuration: str,
            add_low_power_mode: bool,
            x11_forward: bool,
            install_beats_deps: bool,
            beats_workspace: Path,
        ) -> None:
            recorded_call.update(
                {
                    "configuration": configuration,
                    "add_low_power_mode": add_low_power_mode,
                    "x11_forward": x11_forward,
                    "install_beats_deps": install_beats_deps,
                    "beats_workspace": beats_workspace,
                }
            )

        monkeypatch.setattr(
            "heart.cli.commands.run_beats.run_beats_command",
            _fake_run_beats_command,
        )

        result = runner.invoke(
            loop.app,
            [
                "run",
                "--with-beats",
                "--configuration",
                "lib_2025",
                "--no-add-low-power-mode",
                "--x11-forward",
                "--no-install-beats-deps",
                "--beats-workspace",
                "/tmp/beats",
            ],
        )

        assert result.exit_code == 0
        assert recorded_call == {
            "configuration": "lib_2025",
            "add_low_power_mode": False,
            "x11_forward": True,
            "install_beats_deps": False,
            "beats_workspace": Path("/tmp/beats"),
        }

    def test_cli_hides_run_beats_subcommand(self) -> None:
        """Verify the top-level CLI no longer advertises a separate Beats command so opt-in flows consistently use `run --with-beats`."""

        result = runner.invoke(loop.app, ["--help"])

        assert result.exit_code == 0
        assert "run-beats" not in result.stdout

    def test_run_command_skips_beats_launcher_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify plain `run` stays on the core runtime path so default sessions avoid Beats-only dependencies and side effects."""

        monkeypatch.setattr(
            run_module,
            "build_game_loop_container",
            lambda *, x11_forward: _FakeResolver(),
        )

        def _unexpected_run_beats_command(**kwargs: object) -> None:
            raise AssertionError("run_beats_command should not execute without --with-beats")

        monkeypatch.setattr(
            "heart.cli.commands.run_beats.run_beats_command",
            _unexpected_run_beats_command,
        )

        run_module.run_command()


class _FakeResolver:
    """Stub runtime resolver used to exercise the non-Beats command path without booting the full game loop."""

    def __init__(self) -> None:
        self._loop = _FakeGameLoop()
        self._registry = _FakeConfigurationRegistry()

    def resolve(self, dependency: type[object]) -> object:
        if dependency.__name__ == "ConfigurationRegistry":
            return self._registry
        if dependency.__name__ == "GameLoop":
            return self._loop
        raise AssertionError(f"Unexpected dependency: {dependency}")


class _FakeConfigurationRegistry:
    """Stub configuration registry that returns a no-op configuration callback."""

    def get(self, configuration: str) -> object:
        assert configuration == "lib_2025"
        return lambda loop: None


class _FakeGameLoop:
    """Stub game loop that records low-power handling and start calls for command-path validation."""

    def __init__(self) -> None:
        self.add_sleep_mode_called = False
        self.start_called = False

    def add_sleep_mode(self) -> None:
        self.add_sleep_mode_called = True

    def start(self) -> None:
        self.start_called = True
