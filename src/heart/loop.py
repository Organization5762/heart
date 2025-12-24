import os

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

from typing import Annotated

import typer
from PIL import Image

from heart.device import Cube, Device, Rectangle
from heart.device.local import LocalScreen
from heart.environment import GameLoop, RendererVariant
from heart.manage.update import main as update_driver_main
from heart.peripheral.core.providers import container
from heart.programs.registry import ConfigurationRegistry
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

app = typer.Typer()


def _resolve_orientation(
    layout_columns: int | None, layout_rows: int | None
) -> Cube | Rectangle:
    config_columns = Configuration.layout_columns()
    config_rows = Configuration.layout_rows()
    if layout_columns is None:
        layout_columns = config_columns
    if layout_rows is None:
        layout_rows = config_rows

    if (layout_columns is None) ^ (layout_rows is None):
        raise ValueError("Both layout_columns and layout_rows must be set together")
    if layout_columns is not None and layout_rows is not None:
        return Rectangle.with_layout(layout_columns, layout_rows)
    return Cube.sides()


def _get_device(
    x11_forward: bool, *, layout_columns: int | None, layout_rows: int | None
) -> Device:
    orientation = _resolve_orientation(layout_columns, layout_rows)
    device: Device

    if Configuration.forward_to_beats_app():
        from heart.device.beats import StreamedScreen

        return StreamedScreen(orientation=orientation)

    if Configuration.use_isolated_renderer():
        if x11_forward:
            logger.warning("USE_ISOLATED_RENDERER enabled; ignoring x11_forward flag")
        from heart.device.rgb_display import LEDMatrix

        return LEDMatrix(orientation=orientation)
    if Configuration.is_pi():
        import os

        os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"

        pi_info = Configuration.pi()
        if pi_info is not None and pi_info.version > 4:
            logger.warning(
                f"Shit not guaranteed to work Pi5 and higher. Detected: {pi_info}"
            )

        if Configuration.is_x11_forward():
            # This makes it work on Pi when no screens are connected.
            # You need to setup X11 forwarding with XQuartz to do that.
            logger.warning("X11_FORWARD set, running with `LocalScreen`")
            device = LocalScreen(width=64, height=64, orientation=orientation)
        else:
            from heart.device.rgb_display import LEDMatrix

            device = LEDMatrix(orientation=orientation)
    else:
        device = LocalScreen(width=64, height=64, orientation=orientation)
    return device


def _parse_render_variant(value: str) -> RendererVariant:
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("HEART_RENDER_VARIANT must not be empty")
    try:
        return RendererVariant[normalized]
    except KeyError as exc:
        options = ", ".join(variant.name.lower() for variant in RendererVariant)
        raise ValueError(
            f"Unknown render variant '{value}'. Expected one of: {options}"
        ) from exc


@app.command()
def run(
    configuration: Annotated[str, typer.Option("--configuration")] = "lib_2025",
    add_low_power_mode: bool = typer.Option(
        True, "--add-low-power-mode", help="Add a low power mode"
    ),
    x11_forward: bool = typer.Option(
        False, "--x11-forward", help="Use X11 forwarding for RGB display"
    ),
    layout_columns: int | None = typer.Option(
        None, "--layout-columns", help="Number of horizontal panels in the layout"
    ),
    layout_rows: int | None = typer.Option(
        None, "--layout-rows", help="Number of vertical panels in the layout"
    ),
) -> None:
    registry = ConfigurationRegistry()
    configuration_fn = registry.get(configuration)
    if configuration_fn is None:
        raise Exception(f"Configuration '{configuration}' not found in registry")
    render_variant = _parse_render_variant(Configuration.render_variant())
    loop = GameLoop(
        device=_get_device(
            x11_forward, layout_columns=layout_columns, layout_rows=layout_rows
        ),
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
    d = _get_device(x11_forward=False, layout_columns=None, layout_rows=None)

    size = d.full_display_size()
    print(size)

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
