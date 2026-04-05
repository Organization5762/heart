from enum import StrEnum


class DeviceDisplayMode(StrEnum):
    MIRRORED = "mirrored"
    FULL = "full"
    OPENGL = "opengl"

    def to_pygame_mode(self) -> int:
        import pygame

        match self:
            case DeviceDisplayMode.OPENGL:
                return pygame.OPENGL | pygame.DOUBLEBUF
            case DeviceDisplayMode.FULL:
                return pygame.SHOWN
            case DeviceDisplayMode.MIRRORED:
                return pygame.SHOWN
