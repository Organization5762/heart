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
from heart.programs.registry import registry
from heart.utilities.env import Configuration

logger = logging.getLogger(__name__)

app = typer.Typer()


@app.command()
def run(
    configuration: Annotated[str, typer.Option("--configuration")] = "lib_2024",
) -> None:
    configuration_fn = registry.get(configuration)
    if configuration_fn is None:
        raise Exception(f"Configuration '{configuration}' not found in registry")

    # TODO: Re-write this so that there is a local device, as this is broken on local atm
    device = None
    if Configuration.is_pi():
        from heart.device.rgb_display import LEDMatrix

        device = LEDMatrix(chain_length=12)
    else:
        device = LocalScreen(width=64, height=64, orientation=Cube.sides())

    manager = PeripheralManager()
    loop = GameLoop(device=device, peripheral_manager=manager)
    configuration_fn(loop)

    ## ============================= ##
    ## ADD ALL MODES ABOVE THIS LINE ##
    ## ============================= ##
    # Retain an empty loop for "lower power" mode
    mode = loop.add_empty_mode()
    mode.add_renderer(RenderColor(Color(0, 0, 0)))
    ##
    # If on PI, start the sensors.  These should be stubbed out locally
    ##
    # TODO: I want to split this out of the core loop so that
    # there is a more centralized configuration / management of all these IO devices
    loop.start()


@app.command()
def update_driver(name: Annotated[str, typer.Option("--name")]) -> None:
    update_driver_main(device_driver_name=name)


def main():
    return app()


if __name__ == "__main__":
    main()
