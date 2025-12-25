from heart.utilities.env.assets import AssetsConfiguration
from heart.utilities.env.color import ColorConfiguration
from heart.utilities.env.device_layout import DeviceLayoutConfiguration
from heart.utilities.env.reactivex import ReactivexConfiguration
from heart.utilities.env.rendering import RenderingConfiguration
from heart.utilities.env.streaming import StreamingConfiguration
from heart.utilities.env.system import SystemConfiguration


class Configuration(
    SystemConfiguration,
    DeviceLayoutConfiguration,
    ReactivexConfiguration,
    RenderingConfiguration,
    ColorConfiguration,
    AssetsConfiguration,
    StreamingConfiguration,
):
    """Aggregate environment configuration helpers."""
