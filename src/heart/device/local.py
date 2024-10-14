from dataclasses import dataclass
from PIL import Image

from heart.device import Device

@dataclass
class LocalScreen(Device):
    width: int
    height: int

    # TODO:
    def individual_display_size(self) -> tuple[int, int]:
        return (self.width, self.height)
    
    def full_display_size(self) -> tuple[int, int]:
        return (self.width, self.height)
    
    def display_count(self) -> tuple[int, int]:
        return (1, 1)
    
    def get_scale_factor(self) -> int:
        return 5
    
    def set_image(self, image: Image.Image) -> None:
        return super().set_image(image)