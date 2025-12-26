from heart.utilities.env.assets import AssetsConfiguration
from heart.utilities.env.color import ColorConfiguration
from heart.utilities.env.device_layout import DeviceLayoutConfiguration
from heart.utilities.env.mandelbrot import MandelbrotConfiguration
from heart.utilities.env.peripheral import PeripheralConfiguration
from heart.utilities.env.reactivex import ReactivexConfiguration
from heart.utilities.env.rendering import RenderingConfiguration
from heart.utilities.env.system import SystemConfiguration


class Configuration(
    SystemConfiguration,
    DeviceLayoutConfiguration,
    ReactivexConfiguration,
    PeripheralConfiguration,
    RenderingConfiguration,
    ColorConfiguration,
    AssetsConfiguration,
    MandelbrotConfiguration,
):
    """Aggregate environment configuration helpers."""
