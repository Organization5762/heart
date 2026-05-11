from pathlib import Path
from typing import Annotated

import typer

import heart.cli.commands.run_beats as run_beats
from heart.cli.commands.game_loop import build_game_loop_container
from heart.cli.commands.run_options import (DEFAULT_ADD_LOW_POWER_MODE,
                                            DEFAULT_BEATS_WORKSPACE,
                                            DEFAULT_CONFIGURATION,
                                            DEFAULT_INSTALL_BEATS_DEPS,
                                            DEFAULT_WITH_BEATS,
                                            resolve_configuration_name)
from heart.programs.registry import ConfigurationRegistry
from heart.runtime.game_loop import GameLoop
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
        typer.Option("--with-beats", help="Launch the Beats UI alongside the runtime."),
    ] = DEFAULT_WITH_BEATS,
    install_beats_deps: Annotated[
        bool,
        typer.Option(
            "--install-beats-deps/--no-install-beats-deps",
            help="Install Beats node dependencies when node_modules is missing.",
        ),
    ] = DEFAULT_INSTALL_BEATS_DEPS,
    beats_workspace: Annotated[
        Path, typer.Option("--beats-workspace")
    ] = DEFAULT_BEATS_WORKSPACE,
) -> None:
    resolved_configuration = resolve_configuration_name(configuration)

    if with_beats:
        run_beats.run_beats_command(
            configuration=resolved_configuration,
            add_low_power_mode=add_low_power_mode,
            install_beats_deps=install_beats_deps,
            beats_workspace=beats_workspace,
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
    loop.start()
