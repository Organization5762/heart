from typing import Annotated

import typer

from heart.programs.registry import ConfigurationRegistry
from heart.runtime.game_loop import GameLoop
from heart.runtime.launcher import build_game_loop_container
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

DEFAULT_CONFIGURATION = "lib_2025"
DEFAULT_ADD_LOW_POWER_MODE = True
DEFAULT_X11_FORWARD = False


def run_command(
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
) -> None:
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
        loop.app_controller.add_sleep_mode()
    loop.start()
