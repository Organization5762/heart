import pygame
import os

class Loader:
    @classmethod
    def _resolve_path(cls, path):
        return os.path.join(
            os.path.dirname(__file__),
            path
        )

    @classmethod
    def load(cls, path: str):
        return pygame.image.load(cls._resolve_path(path))

    @classmethod
    def load_spirtesheet(cls, path):
        return spritesheet(cls._resolve_path(path))

# https://www.pygame.org/wiki/Spritesheet
# I copied this from here it is kinda meh lol
class spritesheet(object):
    def __init__(self, filename):
        self.sheet = pygame.image.load(filename).convert()

    def image_at(self, rectangle, colorkey = None):
        "Loads image from x,y,x+offset,y+offset"
        rect = pygame.Rect(rectangle)
        image = pygame.Surface(rect.size)
        image.blit(self.sheet, (0, 0), rect)
        if colorkey is not None:
            if colorkey is -1:
                colorkey = image.get_at((0,0))
            image.set_colorkey(colorkey, pygame.RLEACCEL)
        return image

    def images_at(self, rects, colorkey = None):
        "Loads multiple images, supply a list of coordinates"
        return [self.image_at(rect, colorkey) for rect in rects]

    def load_strip(self, rect, image_count, colorkey = None):
        "Loads a strip of images and returns them as a list"
        tups = [(rect[0]+rect[2]*x, rect[1], rect[2], rect[3])
                for x in range(image_count)]
        return self.images_at(tups, colorkey)