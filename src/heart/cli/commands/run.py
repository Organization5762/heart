from pathlib import Path
from typing import Annotated

import typer

import heart.cli.commands.run_beats as run_beats
from heart.cli.commands.game_loop import build_game_loop_container
from heart.cli.commands.run_options import (DEFAULT_ADD_LOW_POWER_MODE,
                                            DEFAULT_BEATS_RUNTIME_HOST,
                                            DEFAULT_BEATS_RUNTIME_PORT,
                                            DEFAULT_BEATS_WEB_HOST,
                                            DEFAULT_BEATS_WEB_PORT,
                                            DEFAULT_BEATS_WORKSPACE,
                                            DEFAULT_CONFIGURATION,
                                            DEFAULT_INSTALL_BEATS_DEPS,
                                            DEFAULT_LOCAL_BEATS_RUNTIME,
                                            DEFAULT_WITH_BEATS,
                                            beats_web_enabled,
                                            resolve_configuration_name)
from heart.programs.registry import ConfigurationRegistry
from heart.runtime.game_loop import GameLoop
from heart.runtime.manyfold_signer import ManyfoldSignerRuntime
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


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
    with_beats: Annotated[
        bool,
        typer.Option(
            "--with-beats",
            help="Launch the browser-served Beats UI alongside the runtime.",
        ),
    ] = DEFAULT_WITH_BEATS,
    with_beats_web: Annotated[
        bool,
        typer.Option(
            "--with-beats-web",
            help="Alias for --with-beats.",
        ),
    ] = False,
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
            help="Start the local runtime for Beats or connect the UI to an existing runtime.",
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

    if with_beats or with_beats_web or beats_web_enabled():
        run_beats.run_beats_web_command(
            configuration=resolved_configuration,
            add_low_power_mode=add_low_power_mode,
            install_beats_deps=install_beats_deps,
            local_runtime=local_runtime,
            beats_runtime_host=beats_runtime_host,
            beats_runtime_port=beats_runtime_port,
            beats_workspace=beats_workspace,
            web_host=beats_web_host,
            web_port=beats_web_port,
        )
        return

    resolver = build_game_loop_container()
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
    signer_runtime = ManyfoldSignerRuntime()
    try:
        signer_runtime.start()
        loop.start()
    finally:
        signer_runtime.close()
