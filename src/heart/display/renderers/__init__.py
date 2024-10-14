class BaseRenderer:
    def __init__(self, *args, **kwargs) -> None:
        self.device_display_mode = "mirrored"

    def process(self, window) -> None:
        None
