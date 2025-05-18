import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import importlib
from typing import Annotated

import typer

from heart.device import Cube, Device
from heart.device.local import LocalScreen
from heart.display.color import Color
from heart.display.renderers.color import RenderColor
from heart.environment import GameLoop
from heart.manage.update import main as update_driver_main
from heart.peripheral.core.manager import PeripheralManager
from heart.programs.registry import ConfigurationRegistry
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

app = typer.Typer()


def _get_device(x11_forward: bool) -> Device:
    # TODO: Add a way of adding orientation either from Config or `run`
    orientation = Cube.sides()
    if Configuration.is_pi():
        if (pi := Configuration.pi()).version > 4:
            print(
                f"""!!!!!!!!!!!!!!!!!!!!
                Everything is only supported on Pi 4 and below. Detected: {pi}
!!!!!!!!!!!!!!!!!!!!!"""
            )

        if Configuration.is_x11_forward():
            # This makes it work on Pi when no screens are connected.
            # You need to setup X11 forwarding with XQuartz to do that.
            logger.warning("RGB display not found, using local screen")
            device = LocalScreen(width=64, height=64, orientation=orientation)
        else:
            from heart.device.rgb_display import LEDMatrix

            device = LEDMatrix(orientation=orientation)
    else:
        device = LocalScreen(width=64, height=64, orientation=orientation)
    return device


@app.command()
def run(
    configuration: Annotated[str, typer.Option("--configuration")] = "lib_2025",
    add_low_power_mode: bool = typer.Option(
        True, "--add-low-power-mode", help="Add a low power mode"
    ),
    x11_forward: bool = typer.Option(
        False, "--x11-forward", help="Use X11 forwarding for RGB display"
    ),
) -> None:
    registry = ConfigurationRegistry()
    configuration_fn = registry.get(configuration)
    if configuration_fn is None:
        raise Exception(f"Configuration '{configuration}' not found in registry")

    manager = PeripheralManager()
    loop = GameLoop(device=_get_device(x11_forward), peripheral_manager=manager)
    configuration_fn(loop)

    ## ============================= ##
    ## ADD ALL MODES ABOVE THIS LINE ##
    ## ============================= ##
    # Retain an empty loop for "lower power" mode
    if add_low_power_mode:
        loop.app_controller.add_sleep_mode()
    loop.start()


@app.command(
    name="test-renderer",
)
def test_renderer(
    renderer_name: Annotated[
        str, typer.Option("--renderer", help="Renderer class name")
    ] = "heart.display.renderers.tixyland:Tixyland",
    add_low_power_mode: bool = typer.Option(
        True, "--add-low-power-mode", help="Add a low power mode"
    ),
    x11_forward: bool = typer.Option(
        False, "--x11-forward", help="Use X11 forwarding for RGB display"
    ),
) -> None:
    module_name, class_name = renderer_name.split(":")
    module = importlib.import_module(module_name)
    renderer_class = getattr(module, class_name)
    renderer = renderer_class()
    loop = GameLoop(
        device=_get_device(x11_forward), peripheral_manager=PeripheralManager()
    )
    loop.app_controller.add_mode(renderer)
    loop.start()


@app.command()
def update_driver(name: Annotated[str, typer.Option("--name")]) -> None:
    update_driver_main(device_driver_name=name)


def main():
    return app()


if __name__ == "__main__":
    main()
