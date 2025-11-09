from __future__ import annotations

from PIL import Image

from heart.device.single_led import SingleLEDDevice
from heart.events.types import DisplayFrame
from heart.peripheral.average_color_led import AverageColorLED


def _register_average(loop) -> tuple[SingleLEDDevice, AverageColorLED]:
    single_led = SingleLEDDevice()
    average_led = AverageColorLED(
        device=single_led,
        source_display=loop.display_peripheral,
    )
    loop.peripheral_manager.register(average_led)
    return single_led, average_led


def test_average_led_tracks_latest_frame(loop) -> None:
    single_led, _ = _register_average(loop)
    image = Image.new("RGB", loop.device.full_display_size(), (255, 0, 0))

    loop.display_peripheral.publish_image(image)

    assert single_led.last_color == (255, 0, 0)


def test_average_led_computes_mean_colour(loop) -> None:
    single_led, _ = _register_average(loop)
    width, height = loop.device.full_display_size()
    image = Image.new("RGB", (width, height))
    image.paste((255, 0, 0), (0, 0, width // 2, height))
    image.paste((0, 0, 255), (width // 2, 0, width, height))

    loop.display_peripheral.publish_image(image)

    assert single_led.last_color == (128, 0, 128)


def test_average_led_ignores_other_displays(loop) -> None:
    single_led, _ = _register_average(loop)
    width, height = loop.device.full_display_size()
    alien_frame = DisplayFrame.from_image(
        Image.new("RGB", (width, height), (0, 255, 0)),
        frame_id=99,
    )

    loop.event_bus.emit(alien_frame.to_input(producer_id=999))

    assert single_led.last_color is None

    loop.display_peripheral.publish_image(
        Image.new("RGB", (width, height), (0, 255, 0))
    )

    assert single_led.last_color == (0, 255, 0)
