from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Annotated

import typer

from heart.cli.commands.run import (
    DEFAULT_ADD_LOW_POWER_MODE,
    DEFAULT_BEATS_WORKSPACE,
    DEFAULT_CONFIGURATION,
    DEFAULT_INSTALL_BEATS_DEPS,
    DEFAULT_X11_FORWARD,
    resolve_configuration_name,
)
from heart.device.beats.websocket import (
    DEFAULT_WEBSOCKET_HOST,
    DEFAULT_WEBSOCKET_PORT,
    websocket_url,
)
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

DEFAULT_BEATS_START_SCRIPT = "start"
DEFAULT_BEATS_WEB_START_SCRIPT = "web"
DEFAULT_BEATS_WEB_HOST = "0.0.0.0"
DEFAULT_BEATS_WEB_PORT = 5173
FORWARD_TO_BEATS_ENV_VAR = "FORWARD_TO_BEATS_APP"
BEATS_WEBSOCKET_ENV_VAR = "VITE_BEATS_WEBSOCKET_URL"
BEATS_WEBSOCKET_HOST_ENV_VAR = "VITE_BEATS_WEBSOCKET_HOST"
BEATS_WEBSOCKET_PORT_ENV_VAR = "VITE_BEATS_WEBSOCKET_PORT"
RUNTIME_WEBSOCKET_PORT_ENV_VAR = "BEATS_WEBSOCKET_PORT"
WEBSOCKET_BIND_HOST_ENV_VAR = "BEATS_WEBSOCKET_BIND_HOST"
LAN_BIND_HOST = "0.0.0.0"
PROCESS_POLL_INTERVAL_SECONDS = 0.5
PROCESS_SHUTDOWN_TIMEOUT_SECONDS = 5.0
_SIGHUP = getattr(signal, "SIGHUP", None)
SIGNAL_EXIT_CODES = {
    signal.SIGINT: 130,
    signal.SIGTERM: 143,
}
if _SIGHUP is not None:
    SIGNAL_EXIT_CODES[_SIGHUP] = 129


def run_beats_command(
    configuration: Annotated[
        str, typer.Option("--configuration")
    ] = DEFAULT_CONFIGURATION,
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
    local_runtime: bool = typer.Option(
        True,
        "--local-runtime/--remote-runtime",
        help="Start the local runtime or connect the Beats UI to an already running runtime.",
    ),
    beats_runtime_host: str = typer.Option(
        DEFAULT_WEBSOCKET_HOST,
        "--beats-runtime-host",
        help="Hostname the Beats UI should use when opening the runtime websocket.",
    ),
    beats_runtime_port: int = typer.Option(
        DEFAULT_WEBSOCKET_PORT,
        "--beats-runtime-port",
        min=1,
        help="Port the Beats UI should use when opening the runtime websocket.",
    ),
    beats_workspace: Annotated[
        Path, typer.Option("--beats-workspace")
    ] = DEFAULT_BEATS_WORKSPACE,
) -> None:
    configuration = resolve_configuration_name(configuration)
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

    websocket_connection_url = build_beats_websocket_url(
        host=beats_runtime_host,
        port=beats_runtime_port,
    )
    beats_command = build_beats_start_command(resolved_beats_workspace)
    beats_env = build_beats_env(
        os.environ.copy(),
        websocket_url=websocket_connection_url,
    )

    if local_runtime:
        runtime_command = build_totem_run_command(
            configuration=configuration,
            add_low_power_mode=add_low_power_mode,
            x11_forward=x11_forward,
        )
        runtime_env = build_runtime_env(
            os.environ.copy(),
            websocket_port=beats_runtime_port,
        )
        exit_code = run_supervised_processes(
            repo_root=repo_root,
            runtime_command=runtime_command,
            runtime_env=runtime_env,
            beats_workspace=resolved_beats_workspace,
            beats_command=beats_command,
            beats_env=beats_env,
        )
    else:
        exit_code = run_single_process(
            process_label="Beats UI",
            command=beats_command,
            cwd=resolved_beats_workspace,
            env=beats_env,
        )
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


def run_beats_web_command(
    *,
    configuration: str = DEFAULT_CONFIGURATION,
    add_low_power_mode: bool = DEFAULT_ADD_LOW_POWER_MODE,
    x11_forward: bool = DEFAULT_X11_FORWARD,
    install_beats_deps: bool = DEFAULT_INSTALL_BEATS_DEPS,
    local_runtime: bool = True,
    beats_runtime_host: str = DEFAULT_WEBSOCKET_HOST,
    beats_runtime_port: int = DEFAULT_WEBSOCKET_PORT,
    beats_workspace: Path = DEFAULT_BEATS_WORKSPACE,
    web_host: str = DEFAULT_BEATS_WEB_HOST,
    web_port: int = DEFAULT_BEATS_WEB_PORT,
) -> None:
    """Launch the browser-served Beats UI instead of the Electron shell."""

    configuration = resolve_configuration_name(configuration)
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

    beats_command = build_beats_web_command(host=web_host, port=web_port)
    beats_env = build_beats_web_env(
        os.environ.copy(),
        websocket_host=beats_runtime_host,
        websocket_port=beats_runtime_port,
    )
    logger.info(
        "Beats web UI will be served on http://localhost:%d. Use your machine's LAN IP with the same port from another device on the same Wi-Fi.",
        web_port,
    )

    if local_runtime:
        runtime_command = build_totem_run_command(
            configuration=configuration,
            add_low_power_mode=add_low_power_mode,
            x11_forward=x11_forward,
        )
        runtime_env = build_runtime_env(
            os.environ.copy(),
            websocket_bind_host=LAN_BIND_HOST,
            websocket_port=beats_runtime_port,
        )
        exit_code = run_supervised_processes(
            repo_root=repo_root,
            runtime_command=runtime_command,
            runtime_env=runtime_env,
            beats_workspace=resolved_beats_workspace,
            beats_command=beats_command,
            beats_env=beats_env,
            ui_label="Beats Web UI",
            startup_message=(
                "Starting Beats Web UI. Open the served URL in a desktop browser or on a phone connected to the same Wi-Fi network."
            ),
        )
    else:
        exit_code = run_single_process(
            process_label="Beats Web UI",
            command=beats_command,
            cwd=resolved_beats_workspace,
            env=beats_env,
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


def build_beats_websocket_url(
    *, host: str = DEFAULT_WEBSOCKET_HOST, port: int = DEFAULT_WEBSOCKET_PORT
) -> str:
    """Build the websocket URL expected by the Beats UI."""

    return websocket_url(host=host, port=port)


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


def build_beats_start_command(beats_workspace: Path) -> list[str]:
    """Build the command that launches the Beats Electron app.

    Prefer ``node`` + the Forge CLI entrypoint over ``npm run start`` so the
    spawned process stays alive for the full Electron session. In some setups
    the ``npm`` wrapper can exit while Electron is still starting, which makes
    the combined launcher think Beats finished and then tears down the runtime.
    """

    forge_entry = (
        beats_workspace
        / "node_modules"
        / "@electron-forge"
        / "cli"
        / "dist"
        / "electron-forge.js"
    )
    if forge_entry.is_file():
        return ["node", str(forge_entry), "start"]
    return ["npm", "run", DEFAULT_BEATS_START_SCRIPT]


def build_beats_web_command(*, host: str, port: int) -> list[str]:
    """Build the command that launches the browser-served Beats UI."""

    return [
        "npm",
        "run",
        DEFAULT_BEATS_WEB_START_SCRIPT,
        "--",
        "--host",
        host,
        "--port",
        str(port),
        "--strictPort",
    ]


def build_runtime_env(
    base_env: dict[str, str],
    *,
    websocket_bind_host: str | None = None,
    websocket_port: int | None = None,
) -> dict[str, str]:
    """Prepare runtime environment variables for Beats forwarding."""

    runtime_env = dict(base_env)
    runtime_env[FORWARD_TO_BEATS_ENV_VAR] = "1"
    if websocket_bind_host is not None:
        runtime_env[WEBSOCKET_BIND_HOST_ENV_VAR] = websocket_bind_host
    if websocket_port is not None:
        runtime_env[RUNTIME_WEBSOCKET_PORT_ENV_VAR] = str(websocket_port)
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


def build_beats_web_env(
    base_env: dict[str, str],
    *,
    websocket_host: str,
    websocket_port: int,
) -> dict[str, str]:
    """Prepare web Beats environment variables for websocket connectivity."""

    beats_env = dict(base_env)
    beats_env[BEATS_WEBSOCKET_PORT_ENV_VAR] = str(websocket_port)

    if websocket_host not in {DEFAULT_WEBSOCKET_HOST, "127.0.0.1"}:
        beats_env[BEATS_WEBSOCKET_HOST_ENV_VAR] = websocket_host
    else:
        beats_env.pop(BEATS_WEBSOCKET_HOST_ENV_VAR, None)

    beats_env.pop(BEATS_WEBSOCKET_ENV_VAR, None)
    return beats_env


def run_supervised_processes(
    *,
    repo_root: Path,
    runtime_command: list[str],
    runtime_env: dict[str, str],
    beats_workspace: Path,
    beats_command: list[str],
    beats_env: dict[str, str],
    ui_label: str = "Beats UI",
    startup_message: str | None = None,
) -> int:
    """Launch the runtime and a Beats-facing UI together."""

    logger.info("Starting totem runtime: %s", " ".join(runtime_command))
    runtime_process = spawn_process(runtime_command, cwd=repo_root, env=runtime_env)
    beats_process: subprocess.Popen[bytes] | None = None

    try:
        if startup_message is not None:
            logger.info(startup_message)
        logger.info("Starting %s: %s", ui_label, " ".join(beats_command))
        beats_process = spawn_process(
            beats_command,
            cwd=beats_workspace,
            env=beats_env,
        )
    except Exception:
        terminate_process(runtime_process)
        raise

    with install_supervisor_signal_handlers() as received_signal:
        try:
            while True:
                runtime_return_code = runtime_process.poll()
                if runtime_return_code is not None:
                    logger.info("Totem runtime exited with code %d", runtime_return_code)
                    return runtime_return_code

                assert beats_process is not None
                beats_return_code = beats_process.poll()
                if beats_return_code is not None:
                    logger.info("%s exited with code %d", ui_label, beats_return_code)
                    return beats_return_code

                time.sleep(PROCESS_POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            logger.info(
                "Stopping totem runtime and %s after %s.",
                ui_label,
                signal_name(received_signal),
            )
            return signal_exit_code(received_signal)
        finally:
            if beats_process is not None:
                terminate_process(beats_process)
            terminate_process(runtime_process)


def run_single_process(
    *,
    process_label: str,
    command: list[str],
    cwd: Path,
    env: dict[str, str],
) -> int:
    """Launch one long-running process and keep it alive until it exits."""

    logger.info("Starting %s: %s", process_label, " ".join(command))
    process = spawn_process(command, cwd=cwd, env=env)
    with install_supervisor_signal_handlers() as received_signal:
        try:
            while True:
                return_code = process.poll()
                if return_code is not None:
                    logger.info("%s exited with code %d", process_label, return_code)
                    return return_code
                time.sleep(PROCESS_POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            logger.info(
                "Stopping %s after %s.",
                process_label,
                signal_name(received_signal),
            )
            return signal_exit_code(received_signal)
        finally:
            terminate_process(process)


def spawn_process(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> subprocess.Popen[bytes]:
    """Spawn a long-running subprocess in its own process group."""

    popen_kwargs: dict[str, object] = {
        "cwd": cwd,
        "env": env,
    }
    if os.name == "posix":
        # Keep child processes in the same terminal session so a terminal hangup
        # still reaches the supervisor, while isolating each tree in its own
        # process group for targeted termination.
        popen_kwargs["process_group"] = 0
    else:
        popen_kwargs["start_new_session"] = True
    try:
        return subprocess.Popen(
            command,
            **popen_kwargs,
        )
    except OSError:
        logger.exception("Failed to launch process: %s", " ".join(command))
        raise typer.Exit(code=1) from None


def terminate_process(process: subprocess.Popen[bytes]) -> None:
    """Terminate a process tree without leaving child processes behind."""

    try:
        if hasattr(os, "killpg"):
            os.killpg(process.pid, signal.SIGTERM)
        else:
            if process.poll() is not None:
                return
            process.terminate()
        process.wait(timeout=PROCESS_SHUTDOWN_TIMEOUT_SECONDS)
    except ProcessLookupError:
        return
    except subprocess.TimeoutExpired:
        if hasattr(os, "killpg"):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                return
        else:
            process.kill()
        process.wait(timeout=PROCESS_SHUTDOWN_TIMEOUT_SECONDS)


def _normalize_signal(signum: int | list[int] | None) -> int | None:
    if isinstance(signum, list):
        if not signum:
            return None
        return signum[-1]
    return signum


def signal_name(signum: int | list[int] | None) -> str:
    signum = _normalize_signal(signum)
    if signum is None:
        return "KeyboardInterrupt"
    try:
        return signal.Signals(signum).name
    except ValueError:
        return f"signal {signum}"


def signal_exit_code(signum: int | list[int] | None) -> int:
    signum = _normalize_signal(signum)
    if signum is None:
        return 130
    return SIGNAL_EXIT_CODES.get(signum, 128 + signum)


@contextmanager
def install_supervisor_signal_handlers() -> Iterator[list[int]]:
    received: list[int] = []
    handled_signals = [signal.SIGINT, signal.SIGTERM]
    if _SIGHUP is not None:
        handled_signals.append(_SIGHUP)

    previous_handlers: dict[int, object] = {}

    def _handle_signal(signum: int, _frame: object) -> None:
        received.append(signum)
        raise KeyboardInterrupt

    for handled_signal in handled_signals:
        previous_handlers[handled_signal] = signal.getsignal(handled_signal)
        signal.signal(handled_signal, _handle_signal)

    try:
        yield received
    finally:
        for handled_signal, previous_handler in previous_handlers.items():
            signal.signal(handled_signal, previous_handler)
