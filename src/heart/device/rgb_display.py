import argparse
import sys
import queue
import threading
from typing import Optional

import queue
import threading
from typing import Optional

from PIL import Image

from heart.device import Device, Layout, Orientation


class SampleBase(object):
    def __init__(self, *args, **kwargs) -> None:
        self.parser = argparse.ArgumentParser()

        self.parser.add_argument(
            "-r",
            "--led-rows",
            action="store",
            help="Display rows. 16 for 16x32, 32 for 32x32. Default: 32",
            default=32,
            type=int,
        )
        self.parser.add_argument(
            "--led-cols",
            action="store",
            help="Panel columns. Typically 32 or 64. (Default: 32)",
            default=32,
            type=int,
        )
        self.parser.add_argument(
            "-c",
            "--led-chain",
            action="store",
            help="Daisy-chained boards. Default: 1.",
            default=1,
            type=int,
        )
        self.parser.add_argument(
            "-P",
            "--led-parallel",
            action="store",
            help="For Plus-models or RPi2: parallel chains. 1..3. Default: 1",
            default=1,
            type=int,
        )
        self.parser.add_argument(
            "-p",
            "--led-pwm-bits",
            action="store",
            help="Bits used for PWM. Something between 1..11. Default: 11",
            default=11,
            type=int,
        )
        self.parser.add_argument(
            "-b",
            "--led-brightness",
            action="store",
            help="Sets brightness level. Default: 100. Range: 1..100",
            default=100,
            type=int,
        )
        #         options.rows = self.row_size
        # options.cols = self.col_size
        # options.chain_length = self.chain_length
        # options.parallel = 1
        # options.pwm_bits = 11

        # options.row_address_type = 0
        # options.multiplexing = 0
        # options.brightness = 100
        # options.pwm_lsb_nanoseconds = 130
        # options.led_rgb_sequence = "RGB"
        # options.pixel_mapper_config = ""
        # options.panel_type = ""
        # options.gpio_slowdown = 4
        # # I hate this option.
        # options.drop_privileges = False
        self.parser.add_argument(
            "-m",
            "--led-gpio-mapping",
            help="Hardware Mapping: regular, adafruit-hat, adafruit-hat-pwm",
            choices=["regular", "regular-pi1", "adafruit-hat", "adafruit-hat-pwm"],
            type=str,
        )
        self.parser.add_argument(
            "--led-scan-mode",
            action="store",
            help="Progressive or interlaced scan. 0 Progressive, 1 Interlaced (default)",
            default=1,
            choices=range(2),
            type=int,
        )
        self.parser.add_argument(
            "--led-pwm-lsb-nanoseconds",
            action="store",
            help="Base time-unit for the on-time in the lowest significant bit in nanoseconds. Default: 130",
            default=130,
            type=int,
        )
        self.parser.add_argument(
            "--led-show-refresh",
            action="store_true",
            help="Shows the current refresh rate of the LED panel",
        )
        self.parser.add_argument(
            "--led-slowdown-gpio",
            action="store",
            help="Slow down writing to GPIO. Range: 0..4. Default: 1",
            default=1,
            type=int,
        )
        self.parser.add_argument(
            "--led-no-hardware-pulse",
            action="store",
            help="Don't use hardware pin-pulse generation",
        )
        self.parser.add_argument(
            "--led-rgb-sequence",
            action="store",
            help="Switch if your matrix has led colors swapped. Default: RGB",
            default="RGB",
            type=str,
        )
        self.parser.add_argument(
            "--led-pixel-mapper",
            action="store",
            help='Apply pixel mappers. e.g "Rotate:90"',
            default="",
            type=str,
        )
        self.parser.add_argument(
            "--led-row-addr-type",
            action="store",
            help="0 = default; 1=AB-addressed panels; 2=row direct; 3=ABC-addressed panels; 4 = ABC Shift + DE direct",
            default=0,
            type=int,
            choices=[0, 1, 2, 3, 4],
        )
        self.parser.add_argument(
            "--led-multiplexing",
            action="store",
            help="Multiplexing type: 0=direct; 1=strip; 2=checker; 3=spiral; 4=ZStripe; 5=ZnMirrorZStripe; 6=coreman; 7=Kaler2Scan; 8=ZStripeUneven... (Default: 0)",
            default=0,
            type=int,
        )
        self.parser.add_argument(
            "--led-panel-type",
            action="store",
            help="Needed to initialize special panels. Supported: 'FM6126A'",
            default="",
            type=str,
        )
        self.parser.add_argument(
            "--led-no-drop-privs",
            dest="drop_privileges",
            help="Don't drop privileges from 'root' after initializing the hardware.",
            action="store_false",
        )
        self.parser.set_defaults(drop_privileges=True)

    def run(self):
        print("Running")

    def process(self):
        self.args = self.parser.parse_args()

        from rgbmatrix import RGBMatrix, RGBMatrixOptions

        options = RGBMatrixOptions()

        if self.args.led_gpio_mapping is not None:
            options.hardware_mapping = self.args.led_gpio_mapping
        options.rows = self.args.led_rows
        options.cols = self.args.led_cols
        options.chain_length = self.args.led_chain
        options.parallel = self.args.led_parallel
        options.row_address_type = self.args.led_row_addr_type
        options.multiplexing = self.args.led_multiplexing
        options.pwm_bits = self.args.led_pwm_bits
        options.brightness = self.args.led_brightness
        options.pwm_lsb_nanoseconds = self.args.led_pwm_lsb_nanoseconds
        options.led_rgb_sequence = self.args.led_rgb_sequence
        options.pixel_mapper_config = self.args.led_pixel_mapper
        options.panel_type = self.args.led_panel_type

        # if self.args.led_show_refresh:
        #     options.show_refresh_rate = 0

        if self.args.led_slowdown_gpio is not None:
            options.gpio_slowdown = self.args.led_slowdown_gpio
        if self.args.led_no_hardware_pulse:
            options.disable_hardware_pulsing = True
        if not self.args.drop_privileges:
            options.drop_privileges = False

        self.matrix = RGBMatrix(options=options)

        try:
            print("Press CTRL-C to stop sample")
            self.run()
        except KeyboardInterrupt:
            print("Exiting\n")
            sys.exit(0)

        return True


from PIL import Image  # just for the type hint


class MatrixDisplayWorker:
    """Worker thread that handles sending images to the RGB matrix (This was taking up
    ~20-30% of main thread)"""

    def __init__(self, matrix):
        self.matrix = matrix
        self.offscreen = self.matrix.CreateFrameCanvas()
        self.q: queue.Queue[Optional[Image.Image]] = queue.Queue(maxsize=2)
        self._worker = threading.Thread(
            target=self._run, daemon=True, name="matrix display worker"
        )
        self._worker.start()

    def set_image_async(self, img: Image.Image) -> None:
        try:
            self.q.put_nowait(img)
        except queue.Full:
            _ = self.q.get_nowait()
            self.q.put_nowait(img)

    def shutdown(self):
        self.q.put(None)
        self._worker.join()

    def _run(self):
        while True:
            img = self.q.get()
            if img is None:
                break

            self.offscreen.Clear()
            self.offscreen.SetImage(img, 0, 0)
            self.offscreen = self.matrix.SwapOnVSync(self.offscreen)
            self.q.task_done()


class LEDMatrix(Device, SampleBase):
    def __init__(self, orientation: Orientation, *args, **kwargs) -> None:
        Device.__init__(self, orientation=orientation)
        SampleBase.__init__(self, *args, **kwargs)
        assert orientation.layout.rows == 1, "Maximum 1 row supported at the moment"

        self.chain_length = orientation.layout.columns
        self.row_size = 64
        self.col_size = 64

        from rgbmatrix import RGBMatrix, RGBMatrixOptions

        options = RGBMatrixOptions()
        # TODO: Might need to change these if we want N screens
        options.rows = self.row_size
        options.cols = self.col_size
        options.chain_length = self.chain_length
        options.parallel = 1
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
        return Layout(columns=self.chain_length, rows=1)

    def individual_display_size(self) -> tuple[int, int]:
        return (self.col_size, self.row_size)

    def full_display_size(self) -> tuple[int, int]:
        return (self.col_size * self.chain_length, self.row_size)

    def set_display_mode(self, mode: str) -> None:
        self.display_mode = mode

    def set_image(self, image: Image.Image) -> None:
        self.worker.set_image_async(image)
