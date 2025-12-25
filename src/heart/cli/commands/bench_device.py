from PIL import Image

from heart.device.selection import select_device
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


def bench_device_command() -> None:
    device = select_device(x11_forward=False)

    size = device.full_display_size()
    logger.info("Device full display size: %s", size)

    image = Image.new("RGB", size)
    while True:
        for i in range(256):
            for j in range(256):
                for k in range(256):
                    image.putdata([(i, j, k)] * (size[0] * size[1]))
                    device.set_image(image)
