from pathlib import Path
from typing import Annotated

import typer

from heart.cli.commands.game_loop import build_game_loop_container
from heart.programs.registry import ConfigurationRegistry
from heart.runtime.game_loop import GameLoop
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

DEFAULT_CONFIGURATION = "lib_2025"
DEFAULT_ADD_LOW_POWER_MODE = True
DEFAULT_X11_FORWARD = False
DEFAULT_WITH_BEATS = False
DEFAULT_INSTALL_BEATS_DEPS = True
DEFAULT_BEATS_WORKSPACE = Path("experimental/beats")


def run_command(
    configuration: Annotated[str, typer.Option("--configuration")] = DEFAULT_CONFIGURATION,
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
    if with_beats:
        from heart.cli.commands.run_beats import run_beats_command

        run_beats_command(
            configuration=configuration,
            add_low_power_mode=add_low_power_mode,
            x11_forward=x11_forward,
            install_beats_deps=install_beats_deps,
            beats_workspace=beats_workspace,
        )
        return

    resolver = build_game_loop_container(x11_forward=x11_forward)
    registry = resolver.resolve(ConfigurationRegistry)
    configuration_fn = registry.get(configuration)
    if configuration_fn is None:
        logger.error("Configuration '%s' not found in registry", configuration)
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
