from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Annotated

import typer

from heart.cli.commands.run import (DEFAULT_ADD_LOW_POWER_MODE,
                                    DEFAULT_BEATS_WORKSPACE,
                                    DEFAULT_CONFIGURATION,
                                    DEFAULT_INSTALL_BEATS_DEPS,
                                    DEFAULT_X11_FORWARD)
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

DEFAULT_BEATS_START_SCRIPT = "start"
FORWARD_TO_BEATS_ENV_VAR = "FORWARD_TO_BEATS_APP"
BEATS_WEBSOCKET_ENV_VAR = "VITE_BEATS_WEBSOCKET_URL"
PROCESS_POLL_INTERVAL_SECONDS = 0.5
PROCESS_SHUTDOWN_TIMEOUT_SECONDS = 5.0


def run_beats_command(
    configuration: Annotated[str, typer.Option("--configuration")] = DEFAULT_CONFIGURATION,
    add_low_power_mode: bool = typer.Option(
        DEFAULT_ADD_LOW_POWER_MODE,
        "--add-low-power-mode",
        help="Add a low power mode",
    ),
    x11_forward: bool = typer.Option(
        DEFAULT_X11_FORWARD,
        "--x11-forward",
        help="Use X11 forwarding for RGB display",
    ),
    install_beats_deps: bool = typer.Option(
        DEFAULT_INSTALL_BEATS_DEPS,
        "--install-beats-deps/--no-install-beats-deps",
        help="Install Beats node dependencies when node_modules is missing.",
    ),
    beats_workspace: Annotated[Path, typer.Option("--beats-workspace")] = DEFAULT_BEATS_WORKSPACE,
) -> None:
    repo_root = resolve_repo_root()
    resolved_beats_workspace = resolve_beats_workspace(repo_root, beats_workspace)
    validate_beats_workspace(resolved_beats_workspace)

    if install_beats_deps:
        ensure_beats_dependencies(resolved_beats_workspace)
    elif not beats_dependencies_installed(resolved_beats_workspace):
        logger.error(
            "Beats dependencies are missing. Run `npm install --package-lock=false` in %s or re-run with --install-beats-deps.",
            resolved_beats_workspace,
        )
        raise typer.Exit(code=1)

    websocket_url = build_beats_websocket_url()
    runtime_command = build_totem_run_command(
        configuration=configuration,
        add_low_power_mode=add_low_power_mode,
        x11_forward=x11_forward,
    )
    beats_command = build_beats_start_command()
    runtime_env = build_runtime_env(os.environ.copy())
    beats_env = build_beats_env(os.environ.copy(), websocket_url=websocket_url)

    exit_code = run_supervised_processes(
        repo_root=repo_root,
        runtime_command=runtime_command,
        runtime_env=runtime_env,
        beats_workspace=resolved_beats_workspace,
        beats_command=beats_command,
        beats_env=beats_env,
    )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


def resolve_repo_root() -> Path:
    """Resolve the git repository root or fall back to the current working directory."""

    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode == 0:
        return Path(result.stdout.strip())
    return Path.cwd()


def resolve_beats_workspace(repo_root: Path, beats_workspace: Path) -> Path:
    """Resolve the Beats workspace relative to the repository root when needed."""

    if beats_workspace.is_absolute():
        return beats_workspace
    return repo_root / beats_workspace


def validate_beats_workspace(beats_workspace: Path) -> None:
    """Fail fast when the configured Beats workspace is not usable."""

    package_json_path = beats_workspace / "package.json"
    if package_json_path.is_file():
        return
    logger.error(
        "Beats workspace %s does not contain package.json.",
        beats_workspace,
    )
    raise typer.Exit(code=1)


def beats_dependencies_installed(beats_workspace: Path) -> bool:
    """Return True when the Beats workspace already has installed dependencies."""

    return (beats_workspace / "node_modules").is_dir()


def ensure_beats_dependencies(beats_workspace: Path) -> None:
    """Install Beats dependencies when the workspace has not been bootstrapped yet."""

    if beats_dependencies_installed(beats_workspace):
        return

    logger.info(
        "Installing Beats dependencies with `npm install --package-lock=false` in %s",
        beats_workspace,
    )
    try:
        result = subprocess.run(
            ["npm", "install", "--package-lock=false"],
            cwd=beats_workspace,
            check=False,
        )
    except OSError:
        logger.exception("Failed to launch npm while installing Beats dependencies.")
        raise typer.Exit(code=1) from None

    if result.returncode == 0:
        return

    logger.error(
        "Beats dependency installation failed with exit code %d.",
        result.returncode,
    )
    raise typer.Exit(code=result.returncode)


def build_beats_websocket_url() -> str:
    """Build the websocket URL expected by the Beats UI."""

    from heart.device.beats.websocket import WEBSOCKET_HOST, WEBSOCKET_PORT

    return f"ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}"


def build_totem_run_command(
    *,
    configuration: str,
    add_low_power_mode: bool,
    x11_forward: bool,
) -> list[str]:
    """Build the runtime command that forwards frames into Beats."""

    command = ["uv", "run", "totem", "run", "--configuration", configuration]
    if x11_forward:
        command.append("--x11-forward")
    if not add_low_power_mode:
        command.append("--no-add-low-power-mode")
    return command


def build_beats_start_command() -> list[str]:
    """Build the command that launches the Beats Electron app."""

    return ["npm", "run", DEFAULT_BEATS_START_SCRIPT]


def build_runtime_env(base_env: dict[str, str]) -> dict[str, str]:
    """Prepare runtime environment variables for Beats forwarding."""

    runtime_env = dict(base_env)
    runtime_env[FORWARD_TO_BEATS_ENV_VAR] = "1"
    return runtime_env


def build_beats_env(
    base_env: dict[str, str],
    *,
    websocket_url: str,
) -> dict[str, str]:
    """Prepare Beats environment variables for websocket connectivity."""

    beats_env = dict(base_env)
    beats_env[BEATS_WEBSOCKET_ENV_VAR] = websocket_url
    return beats_env


def run_supervised_processes(
    *,
    repo_root: Path,
    runtime_command: list[str],
    runtime_env: dict[str, str],
    beats_workspace: Path,
    beats_command: list[str],
    beats_env: dict[str, str],
) -> int:
    """Launch the runtime and Beats UI together and stop both when either exits."""

    logger.info("Starting totem runtime: %s", " ".join(runtime_command))
    runtime_process = spawn_process(runtime_command, cwd=repo_root, env=runtime_env)

    try:
        logger.info("Starting Beats UI: %s", " ".join(beats_command))
        beats_process = spawn_process(
            beats_command,
            cwd=beats_workspace,
            env=beats_env,
        )
    except Exception:
        terminate_process(runtime_process)
        raise

    try:
        while True:
            runtime_return_code = runtime_process.poll()
            if runtime_return_code is not None:
                logger.info("Totem runtime exited with code %d", runtime_return_code)
                return runtime_return_code

            beats_return_code = beats_process.poll()
            if beats_return_code is not None:
                logger.info("Beats UI exited with code %d", beats_return_code)
                return beats_return_code

            time.sleep(PROCESS_POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logger.info("Stopping totem runtime and Beats UI.")
        return 130
    finally:
        terminate_process(beats_process)
        terminate_process(runtime_process)


def spawn_process(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> subprocess.Popen[bytes]:
    """Spawn a long-running subprocess in its own process group."""

    try:
        return subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            start_new_session=True,
        )
    except OSError:
        logger.exception("Failed to launch process: %s", " ".join(command))
        raise typer.Exit(code=1) from None


def terminate_process(process: subprocess.Popen[bytes]) -> None:
    """Terminate a process tree without leaving child processes behind."""

    if process.poll() is not None:
        return

    try:
        if hasattr(os, "killpg"):
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=PROCESS_SHUTDOWN_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        if hasattr(os, "killpg"):
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait(timeout=PROCESS_SHUTDOWN_TIMEOUT_SECONDS)
