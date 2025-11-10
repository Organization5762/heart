import pygame

from heart import DeviceDisplayMode
from heart.device import Cube
from heart.display.color import Color
from heart.display.renderers.color import RenderColor
from heart.display.renderers.image import RenderImage
from heart.display.renderers.internal.event_stream import \
    RendererEventPublisher
from heart.peripheral.core.event_bus import EventBus
from heart.peripheral.core.manager import PeripheralManager


class TestRendererEventStream:
    """Verify renderer event publishers interoperate with subscribers to harden compositor experiments."""

    def test_publisher_emits_frames_consumed_by_render_image(self) -> None:
        """Ensure renderer frames traverse the event bus so stateful consumers no longer require direct surface injection."""

        pygame.init()
        try:
            bus = EventBus()
            manager = PeripheralManager(event_bus=bus)
            clock = pygame.time.Clock()
            orientation = Cube.sides()

            color_source = RenderColor(Color(24, 48, 96))
            color_source.device_display_mode = DeviceDisplayMode.FULL
            publisher = RendererEventPublisher(
                color_source, channel="renderer://test"
            )
            publisher.device_display_mode = DeviceDisplayMode.FULL
            subscriber = RenderImage(subscribe_channel="renderer://test")
            subscriber.device_display_mode = DeviceDisplayMode.FULL

            # Prime subscriber so the event bus subscription is active before frames publish.
            warmup_surface = pygame.Surface((8, 8), pygame.SRCALPHA)
            subscriber._internal_process(warmup_surface, clock, manager, orientation)

            publisher_surface = pygame.Surface((8, 8), pygame.SRCALPHA)
            publisher._internal_process(publisher_surface, clock, manager, orientation)

            output_surface = pygame.Surface((8, 8), pygame.SRCALPHA)
            subscriber._internal_process(output_surface, clock, manager, orientation)

            assert subscriber.state.image is not None
            assert output_surface.get_at((0, 0))[:3] == (24, 48, 96)
        finally:
            pygame.quit()
