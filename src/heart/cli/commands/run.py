import os
from pathlib import Path
from typing import Annotated

import typer

from heart.cli.commands.game_loop import build_game_loop_container
from heart.programs.registry import ConfigurationRegistry
from heart.runtime.game_loop import GameLoop
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

DEFAULT_CONFIGURATION = "lib_2025"
CONFIGURATION_OVERRIDE_ENV_VAR = "HEART_RUN_CONFIGURATION"
DEFAULT_ADD_LOW_POWER_MODE = True
DEFAULT_X11_FORWARD = False
DEFAULT_WITH_BEATS = False
DEFAULT_WITH_BEATS_WEB = False
DEFAULT_INSTALL_BEATS_DEPS = True
DEFAULT_BEATS_WORKSPACE = Path("experimental/beats")
DEFAULT_LOCAL_BEATS_RUNTIME = True
DEFAULT_BEATS_RUNTIME_HOST = "localhost"
DEFAULT_BEATS_RUNTIME_PORT = 8765
DEFAULT_BEATS_WEB_HOST = "0.0.0.0"
DEFAULT_BEATS_WEB_PORT = 5173


def resolve_configuration_name(configuration: str) -> str:
    """Return the requested configuration after applying any environment override."""

    override = os.environ.get(CONFIGURATION_OVERRIDE_ENV_VAR, "").strip()
    if not override:
        return configuration
    if override != configuration:
        logger.info(
            "Using configuration override from %s: %s",
            CONFIGURATION_OVERRIDE_ENV_VAR,
            override,
        )
    return override


def run_command(
    configuration: Annotated[
        str, typer.Option("--configuration")
    ] = DEFAULT_CONFIGURATION,
    add_low_power_mode: Annotated[
        bool,
        typer.Option(
            "--add-low-power-mode/--no-add-low-power-mode",
            help="Add a low power mode",
        ),
    ] = DEFAULT_ADD_LOW_POWER_MODE,
    x11_forward: Annotated[
        bool,
        typer.Option("--x11-forward", help="Use X11 forwarding for RGB display"),
    ] = DEFAULT_X11_FORWARD,
    with_beats: Annotated[
        bool,
        typer.Option("--with-beats", help="Launch the Beats UI alongside the runtime."),
    ] = DEFAULT_WITH_BEATS,
    with_beats_web: Annotated[
        bool,
        typer.Option(
            "--with-beats-web",
            help="Launch the browser-served Beats UI alongside the runtime.",
        ),
    ] = DEFAULT_WITH_BEATS_WEB,
    install_beats_deps: Annotated[
        bool,
        typer.Option(
            "--install-beats-deps/--no-install-beats-deps",
            help="Install Beats node dependencies when node_modules is missing.",
        ),
    ] = DEFAULT_INSTALL_BEATS_DEPS,
    local_runtime: Annotated[
        bool,
        typer.Option(
            "--local-runtime/--remote-runtime",
            help="Start the local runtime for Beats or connect the Beats UI to an existing remote runtime.",
        ),
    ] = DEFAULT_LOCAL_BEATS_RUNTIME,
    beats_runtime_host: Annotated[
        str,
        typer.Option(
            "--beats-runtime-host",
            help="Hostname the Beats UI should use to reach the runtime websocket.",
        ),
    ] = DEFAULT_BEATS_RUNTIME_HOST,
    beats_runtime_port: Annotated[
        int,
        typer.Option(
            "--beats-runtime-port",
            min=1,
            help="Port the Beats UI should use to reach the runtime websocket.",
        ),
    ] = DEFAULT_BEATS_RUNTIME_PORT,
    beats_workspace: Annotated[
        Path, typer.Option("--beats-workspace")
    ] = DEFAULT_BEATS_WORKSPACE,
    beats_web_host: Annotated[
        str,
        typer.Option(
            "--beats-web-host",
            help="Host interface for the browser-served Beats UI.",
        ),
    ] = DEFAULT_BEATS_WEB_HOST,
    beats_web_port: Annotated[
        int,
        typer.Option(
            "--beats-web-port",
            min=1,
            help="Port for the browser-served Beats UI.",
        ),
    ] = DEFAULT_BEATS_WEB_PORT,
) -> None:
    resolved_configuration = resolve_configuration_name(configuration)

    if with_beats and with_beats_web:
        logger.error("Choose either `--with-beats` or `--with-beats-web`, not both.")
        raise typer.Exit(code=1)

    if with_beats_web:
        from heart.cli.commands.run_beats import run_beats_web_command

        run_beats_web_command(
            configuration=resolved_configuration,
            add_low_power_mode=add_low_power_mode,
            x11_forward=x11_forward,
            install_beats_deps=install_beats_deps,
            local_runtime=local_runtime,
            beats_runtime_host=beats_runtime_host,
            beats_runtime_port=beats_runtime_port,
            beats_workspace=beats_workspace,
            web_host=beats_web_host,
            web_port=beats_web_port,
        )
        return

    if with_beats:
        from heart.cli.commands.run_beats import run_beats_command

        run_beats_command(
            configuration=resolved_configuration,
            add_low_power_mode=add_low_power_mode,
            x11_forward=x11_forward,
            install_beats_deps=install_beats_deps,
            local_runtime=local_runtime,
            beats_runtime_host=beats_runtime_host,
            beats_runtime_port=beats_runtime_port,
            beats_workspace=beats_workspace,
        )
        return

    if os.environ.get("FORWARD_TO_BEATS_APP") != "1":
        logger.info(
            "Beats UI not started. Use `--with-beats` for Electron or `--with-beats-web` for the browser-served UI next to the pygame totem window."
        )
    resolver = build_game_loop_container(x11_forward=x11_forward)
    registry = resolver.resolve(ConfigurationRegistry)
    configuration_fn = registry.get(resolved_configuration)
    if configuration_fn is None:
        logger.error(
            "Configuration '%s' not found in registry",
            resolved_configuration,
        )
        raise typer.Exit(code=1)
    loop = resolver.resolve(GameLoop)
    configuration_fn(loop)

    ## ============================= ##
    ## ADD ALL MODES ABOVE THIS LINE ##
    ## ============================= ##
    # Retain an empty loop for "lower power" mode
    if add_low_power_mode:
        loop.add_sleep_mode()
    loop.start()
