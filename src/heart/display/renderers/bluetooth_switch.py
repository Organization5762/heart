from heart.display.renderers import BaseRenderer
from heart.utilities.logging import get_logger

logger = get_logger(__name__)

class BluetoothSwitchRenderer(BaseRenderer):
    def __init__(self, renderer: BaseRenderer):
        self.renderer = renderer

    def get_renderers(self) -> list[BaseRenderer]:
        return []

    def initialize(self, window: pygame.Surface, clock: pygame.time.Clock, peripheral_manager: PeripheralManager, orientation: Orientation) -> None:
        self.renderer.initialize(window, clock, peripheral_manager, orientation)

    def process(self, screen: pygame.Surface, clock: pygame.time.Clock, peripheral_manager: PeripheralManager, orientation: Orientation) -> None:
        self.renderer.process(screen, clock, peripheral_manager, orientation)
        if peripheral_manager.bluetooth_switch() is None:
            logger.warning("Bluetooth switch not found")
            return
        
        print("FOUND!")