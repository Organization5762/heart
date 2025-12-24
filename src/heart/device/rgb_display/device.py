from typing import Any, Optional

from PIL import Image

from heart.device import Device, Layout, Orientation
from heart.device.rgb_display.isolated_render import MatrixClient
from heart.device.rgb_display.sample_base import SampleBase
from heart.device.rgb_display.worker import MatrixDisplayWorker
from heart.utilities.env import Configuration
from heart.utilities.logging import get_logger

logger = get_logger(__name__)


class LEDMatrix(Device, SampleBase):
    def __init__(self, orientation: Orientation, *args: Any, **kwargs: Any) -> None:
        Device.__init__(self, orientation=orientation)
        SampleBase.__init__(self, *args, **kwargs)

        self.chain_length = orientation.layout.columns
        self.parallel = orientation.layout.rows
        self.row_size = 64
        self.col_size = 64

        self._client: Optional[MatrixClient] = None
        self.worker: Optional[MatrixDisplayWorker] = None
        self.matrix = None

        if Configuration.use_isolated_renderer():
            socket_path = Configuration.isolated_renderer_socket()
            tcp_address = Configuration.isolated_renderer_tcp_address()
            if socket_path and tcp_address:
                logger.warning(
                    "Both socket and TCP configuration detected; defaulting to TCP"
                )
                socket_path = None
            logger.info("Using isolated renderer client for LED matrix output")
            self._client = MatrixClient(
                socket_path=socket_path,
                tcp_address=tcp_address,
            )
        else:
            from rgbmatrix import RGBMatrix, RGBMatrixOptions

            options = RGBMatrixOptions()
            options.rows = self.row_size
            options.cols = self.col_size
            options.chain_length = self.chain_length
            options.parallel = self.parallel
            options.pwm_bits = 11

            options.show_refresh_rate = 1
            # Setting this to True can cause ghosting
            options.disable_hardware_pulsing = False
            options.multiplexing = 0
            options.row_address_type = 0
            options.brightness = 100
            options.led_rgb_sequence = "RGB"

            # These two settings, pwm_lsb_nanoseconds and gpio_slowdown are sometimes associated with ghosting
            # https://github.com/hzeller/rpi-rgb-led-matrix/blob/master/README.md
            options.pwm_lsb_nanoseconds = 100
            options.gpio_slowdown = 4
            options.pixel_mapper_config = ""
            options.panel_type = ""
            # I hate this option.
            options.drop_privileges = False

            self.matrix = RGBMatrix(options=options)
            self.worker = MatrixDisplayWorker(self.matrix)

    def layout(self) -> Layout:
        return Layout(columns=self.chain_length, rows=self.parallel)

    def individual_display_size(self) -> tuple[int, int]:
        return (self.col_size, self.row_size)

    def full_display_size(self) -> tuple[int, int]:
        return (self.col_size * self.chain_length, self.row_size * self.parallel)

    def set_display_mode(self, mode: str) -> None:
        self.display_mode = mode

    def set_image(self, image: Image.Image) -> None:
        if self._client is not None:
            self._client.send_image(image)
        elif self.worker is not None:
            self.worker.set_image_async(image)
        else:
            raise RuntimeError("LEDMatrix is not configured with a renderer")
