import logging
from typing import Annotated

import typer

from heart.device import Cube
from heart.device.local import LocalScreen
from heart.display.color import Color
from heart.display.renderers.color import RenderColor
from heart.environment import GameLoop
from heart.manage.update import main as update_driver_main
from heart.peripheral.manager import PeripheralManager
from heart.programs.registry import ConfigurationRegistry
from heart.utilities.env import Configuration

logger = logging.getLogger(__name__)

app = typer.Typer()


@app.command()
def run(
    configuration: Annotated[str, typer.Option("--configuration")] = "lib_2025",
    x11_forward: bool = typer.Option(
        False, "--x11-forward", help="Use X11 forwarding for RGB display"
    ),
) -> None:
    registry = ConfigurationRegistry()
    configuration_fn = registry.get(configuration)
    if configuration_fn is None:
        raise Exception(f"Configuration '{configuration}' not found in registry")

    # TODO: Add a way of adding orientation either from Config or `run`
    orientation = Cube.sides()
    if Configuration.is_pi():
        if x11_forward:
            # This makes it work on Pi when no screens are connected.
            # You need to setup X11 forwarding with XQuartz to do that.
            logger.warning("RGB display not found, using local screen")
            device = LocalScreen(width=64, height=64, orientation=orientation)
        else:
            from heart.device.rgb_display import LEDMatrix

            device = LEDMatrix(orientation=orientation)
    else:
        device = LocalScreen(width=64, height=64, orientation=orientation)

    manager = PeripheralManager()
    loop = GameLoop(device=device, peripheral_manager=manager)
    configuration_fn(loop)

    ## ============================= ##
    ## ADD ALL MODES ABOVE THIS LINE ##
    ## ============================= ##
    # Retain an empty loop for "lower power" mode))
    loop.start()


@app.command()
def update_driver(name: Annotated[str, typer.Option("--name")]) -> None:
    update_driver_main(device_driver_name=name)


def main():
    return app()


if __name__ == "__main__":
    main()
