from PIL import Image


class Device:
    def individual_display_size(self) -> tuple[int, int]:
        raise NotImplementedError("")

    def full_display_size(self) -> tuple[int, int]:
        raise NotImplementedError("")

    def display_count(self) -> tuple[int, int]:
        return 1, 1

    def get_scale_factor(self) -> int:
        return 1

    def set_image(self, image: Image.Image) -> None:
        pass
