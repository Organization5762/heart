"""Validate the combined totem-plus-Beats launcher so the single-command workflow stays reliable."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from heart import loop
from heart.cli.commands import run as run_module
from heart.cli.commands.run_beats import (BEATS_WEBSOCKET_HOST_ENV_VAR,
                                          BEATS_WEBSOCKET_PORT_ENV_VAR,
                                          BEATS_WEBSOCKET_URL_ENV_VAR,
                                          FORWARD_TO_BEATS_ENV_VAR,
                                          build_beats_web_env,
                                          build_totem_run_command,
                                          ensure_beats_dependencies,
                                          resolve_beats_workspace)
from heart.cli.commands.run_options import CONFIGURATION_OVERRIDE_ENV_VAR

runner = CliRunner()


class TestRunBeatsCommandBuilders:
    """Exercise command and environment builders so the launcher keeps the runtime and UI in sync."""

    def test_build_totem_run_command_includes_requested_flags(self) -> None:
        """Verify runtime flags are preserved so the combined launcher does not silently change scene startup behaviour."""

        command = build_totem_run_command(
            configuration="lib_2025",
            add_low_power_mode=False,
        )

        assert command == [
            "uv",
            "run",
            "totem",
            "run",
            "--configuration",
            "lib_2025",
            "--no-add-low-power-mode",
        ]

    def test_build_beats_web_env_sets_websocket_host_and_port(self) -> None:
        """Verify the Beats web app receives websocket settings so it can attach to the runtime stream immediately on boot."""

        env = build_beats_web_env(
            {"PATH": "/bin", BEATS_WEBSOCKET_URL_ENV_VAR: "ws://stale:8765"},
            websocket_host="totem.local",
            websocket_port=9876,
        )

        assert env[BEATS_WEBSOCKET_HOST_ENV_VAR] == "totem.local"
        assert env[BEATS_WEBSOCKET_PORT_ENV_VAR] == "9876"
        assert BEATS_WEBSOCKET_URL_ENV_VAR not in env
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

        def _unexpected_run(
            *args: object, **kwargs: object
        ) -> subprocess.CompletedProcess[bytes]:
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
    """Validate the opt-in Beats web CLI path so default runtime startup stays independent from the UI bundle."""

    def test_run_command_dispatches_to_beats_only_when_requested(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify `--with-beats` delegates into the Beats web launcher so the UI starts only for explicitly requested sessions."""

        recorded_call: dict[str, object] = {}

        def _fake_run_beats_web_command(
            *,
            configuration: str,
            add_low_power_mode: bool,
            install_beats_deps: bool,
            local_runtime: bool,
            beats_runtime_host: str,
            beats_runtime_port: int,
            beats_workspace: Path,
            web_host: str,
            web_port: int,
        ) -> None:
            recorded_call.update(
                {
                    "configuration": configuration,
                    "add_low_power_mode": add_low_power_mode,
                    "install_beats_deps": install_beats_deps,
                    "local_runtime": local_runtime,
                    "beats_runtime_host": beats_runtime_host,
                    "beats_runtime_port": beats_runtime_port,
                    "beats_workspace": beats_workspace,
                    "web_host": web_host,
                    "web_port": web_port,
                }
            )

        monkeypatch.setattr(
            "heart.cli.commands.run_beats.run_beats_web_command",
            _fake_run_beats_web_command,
        )

        result = runner.invoke(
            loop.app,
            [
                "run",
                "--with-beats",
                "--configuration",
                "lib_2025",
                "--no-add-low-power-mode",
                "--no-install-beats-deps",
                "--beats-workspace",
                "/tmp/beats",
            ],
        )

        assert result.exit_code == 0
        assert recorded_call == {
            "configuration": "lib_2025",
            "add_low_power_mode": False,
            "install_beats_deps": False,
            "local_runtime": True,
            "beats_runtime_host": "localhost",
            "beats_runtime_port": 8765,
            "beats_workspace": Path("/tmp/beats"),
            "web_host": "0.0.0.0",
            "web_port": 5173,
        }

    def test_cli_exposes_run_beats_subcommand(self) -> None:
        """Verify the top-level CLI advertises the documented Beats web quick-start command."""

        result = runner.invoke(loop.app, ["--help"])

        assert result.exit_code == 0
        assert "run-beats" in result.stdout

    def test_run_beats_subcommand_dispatches_to_launcher(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify `totem run-beats` uses the supervised runtime-plus-web-UI launcher."""

        recorded_call: dict[str, object] = {}

        def _fake_run_supervised_processes(**kwargs: object) -> int:
            recorded_call.update(kwargs)
            return 0

        monkeypatch.setattr(
            "heart.cli.commands.run_beats.ensure_beats_dependencies",
            lambda beats_workspace: None,
        )
        monkeypatch.setattr(
            "heart.cli.commands.run_beats.validate_beats_workspace",
            lambda beats_workspace: None,
        )
        monkeypatch.setattr(
            "heart.cli.commands.run_beats.beats_dependencies_installed",
            lambda beats_workspace: True,
        )
        monkeypatch.setattr(
            "heart.cli.commands.run_beats.run_supervised_processes",
            _fake_run_supervised_processes,
        )

        result = runner.invoke(
            loop.app,
            [
                "run-beats",
                "--configuration",
                "lib_2025",
                "--no-add-low-power-mode",
                "--no-install-beats-deps",
                "--beats-workspace",
                "/tmp/beats",
            ],
        )

        assert result.exit_code == 0
        assert recorded_call["runtime_command"] == [
            "uv",
            "run",
            "totem",
            "run",
            "--configuration",
            "lib_2025",
            "--no-add-low-power-mode",
        ]
        assert recorded_call["beats_workspace"] == Path("/tmp/beats")
        assert recorded_call["ui_label"] == "Beats Web UI"

    def test_run_command_skips_beats_launcher_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify plain `run` stays on the core runtime path so default sessions avoid Beats-only dependencies and side effects."""

        monkeypatch.setattr(
            run_module,
            "build_game_loop_container",
            lambda: _FakeResolver(),
        )

        def _unexpected_run_beats_web_command(**kwargs: object) -> None:
            raise AssertionError(
                "run_beats_command should not execute without --with-beats"
            )

        monkeypatch.setattr(
            "heart.cli.commands.run_beats.run_beats_web_command",
            _unexpected_run_beats_web_command,
        )

        run_module.run_command()

    def test_run_command_uses_configuration_override_env_var(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify the runtime honors the top-level configuration override so service restarts can temporarily boot a development mode without changing the command line."""

        resolver = _FakeResolver()
        monkeypatch.setattr(
            run_module,
            "build_game_loop_container",
            lambda: resolver,
        )
        monkeypatch.setenv(
            CONFIGURATION_OVERRIDE_ENV_VAR,
            "rubiks_connected_x_visualizer",
        )

        run_module.run_command()

        assert resolver._registry.last_requested_configuration == (
            "rubiks_connected_x_visualizer"
        )

    def test_run_command_forwards_configuration_override_to_beats(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify the Beats launcher receives the same configuration override so direct and UI-backed sessions stay aligned during temporary development overrides."""

        recorded_call: dict[str, object] = {}

        def _fake_run_beats_web_command(**kwargs: object) -> None:
            recorded_call.update(kwargs)

        monkeypatch.setenv(
            CONFIGURATION_OVERRIDE_ENV_VAR,
            "rubiks_connected_x_visualizer",
        )
        monkeypatch.setattr(
            "heart.cli.commands.run_beats.run_beats_web_command",
            _fake_run_beats_web_command,
        )

        run_module.run_command(with_beats=True)

        assert recorded_call["configuration"] == "rubiks_connected_x_visualizer"

    def test_run_command_keeps_with_beats_web_as_alias(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify the old web-specific flag stays as a compatibility alias after Beats becomes web-only."""

        recorded_call: dict[str, object] = {}

        def _fake_run_beats_web_command(**kwargs: object) -> None:
            recorded_call.update(kwargs)

        monkeypatch.setattr(
            "heart.cli.commands.run_beats.run_beats_web_command",
            _fake_run_beats_web_command,
        )

        run_module.run_command(with_beats_web=True)

        assert recorded_call["configuration"] == "lib_2025"


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

    def __init__(self) -> None:
        self.last_requested_configuration: str | None = None

    def get(self, configuration: str) -> object:
        self.last_requested_configuration = configuration
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
