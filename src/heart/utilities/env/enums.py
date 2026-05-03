from enum import StrEnum


class RenderTileStrategy(StrEnum):
    BLITS = "blits"
    LOOP = "loop"


class AssetCacheStrategy(StrEnum):
    NONE = "none"
    METADATA = "metadata"
    IMAGES = "images"
    SPRITESHEETS = "spritesheets"
    ALL = "all"


class FrameArrayStrategy(StrEnum):
    COPY = "copy"
    VIEW = "view"


class FrameExportStrategy(StrEnum):
    BUFFER = "buffer"
    ARRAY = "array"


class BleUartBufferStrategy(StrEnum):
    BYTES = "bytes"
    TEXT = "text"


class SpritesheetFrameCacheStrategy(StrEnum):
    NONE = "none"
    FRAMES = "frames"
    SCALED = "scaled"


class LifeUpdateStrategy(StrEnum):
    AUTO = "auto"
    CONVOLVE = "convolve"
    PAD = "pad"
    SHIFTED = "shifted"


class LifeRuleStrategy(StrEnum):
    AUTO = "auto"
    DIRECT = "direct"
    TABLE = "table"


class MandelbrotInteriorStrategy(StrEnum):
    NONE = "none"
    CARDIOID = "cardioid"


class DeviceLayoutMode(StrEnum):
    CUBE = "cube"
    RECTANGLE = "rectangle"


class IsolatedRendererAckStrategy(StrEnum):
    ALWAYS = "always"
    NEVER = "never"


class IsolatedRendererDedupStrategy(StrEnum):
    NONE = "none"
    SOURCE = "source"
    PAYLOAD = "payload"
