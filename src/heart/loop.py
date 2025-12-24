import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from typing import Annotated

import typer
from PIL import Image

from heart.device.selection import select_device
from heart.manage.update import main as update_driver_main
from heart.peripheral.core.providers import container
from heart.programs.registry import ConfigurationRegistry
from heart.runtime.game_loop import GameLoop, RendererVariant
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

app = typer.Typer()


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
    render_variant = RendererVariant.parse(Configuration.render_variant())
    loop = GameLoop(
        device=select_device(x11_forward=x11_forward),
        resolver=container,
        render_variant=render_variant,
    )
    configuration_fn(loop)

    ## ============================= ##
    ## ADD ALL MODES ABOVE THIS LINE ##
    ## ============================= ##
    # Retain an empty loop for "lower power" mode
    if add_low_power_mode:
        loop.app_controller.add_sleep_mode()
    loop.start()



@app.command()
def update_driver(name: Annotated[str, typer.Option("--name")]) -> None:
    update_driver_main(device_driver_name=name)


@app.command(
    name="bench-device",
)
def bench_device() -> None:
    d = select_device(x11_forward=False)

    size = d.full_display_size()
    logger.info("Device full display size: %s", size)

    image = Image.new("RGB", size)
    while True:
        for i in range(256):
            for j in range(256):
                for k in range(256):
                    image.putdata([(i, j, k)] * (size[0] * size[1]))
                    d.set_image(image)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
