"""Configuration demonstrating LED matrix mirroring to a single LED."""

from heart.device.single_led import SingleLEDDevice
from heart.display.color import Color
from heart.display.renderers.color import RenderColor
from heart.environment import GameLoop
from heart.peripheral.average_color_led import AverageColorLED


def configure(loop: GameLoop) -> None:
    mode = loop.add_mode("Dual Output Demo")
    mode.add_renderer(RenderColor(color=Color(32, 96, 224)))

    single_led = SingleLEDDevice()
    average_led = AverageColorLED(
        device=single_led,
        source_display=loop.display_peripheral,
    )
    loop.peripheral_manager.register(average_led)
