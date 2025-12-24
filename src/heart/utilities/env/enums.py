from enum import StrEnum


class RenderTileStrategy(StrEnum):
    BLITS = "blits"
    LOOP = "loop"


class RenderMergeStrategy(StrEnum):
    IN_PLACE = "in_place"
    BATCHED = "batched"


class FrameArrayStrategy(StrEnum):
    COPY = "copy"
    VIEW = "view"


class SpritesheetFrameCacheStrategy(StrEnum):
    NONE = "none"
    FRAMES = "frames"
    SCALED = "scaled"


class LifeUpdateStrategy(StrEnum):
    AUTO = "auto"
    CONVOLVE = "convolve"
    PAD = "pad"


class DeviceLayoutMode(StrEnum):
    CUBE = "cube"
    RECTANGLE = "rectangle"


class ReactivexEventBusScheduler(StrEnum):
    INLINE = "inline"
    BACKGROUND = "background"
    INPUT = "input"


class ReactivexStreamShareStrategy(StrEnum):
    SHARE = "share"
    SHARE_AUTO_CONNECT = "share_auto_connect"
    REPLAY_LATEST = "replay_latest"
    REPLAY_LATEST_AUTO_CONNECT = "replay_latest_auto_connect"
    REPLAY_BUFFER = "replay_buffer"
    REPLAY_BUFFER_AUTO_CONNECT = "replay_buffer_auto_connect"


class ReactivexStreamConnectMode(StrEnum):
    LAZY = "lazy"
    EAGER = "eager"
