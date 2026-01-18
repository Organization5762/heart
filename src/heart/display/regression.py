"""Tools for visual regression checks using perceptual hashes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import imagehash
from PIL import Image

if TYPE_CHECKING:  # pragma: no cover - import cycle guard
    from collections.abc import Sequence


@dataclass(frozen=True)
class RegressionComparison:
    """Summary of a perceptual hash comparison."""

    observed_hash: imagehash.ImageHash
    expected_hash: imagehash.ImageHash

    @property
    def distance(self) -> int:
        return self.observed_hash - self.expected_hash

    def within(self, limit: int) -> bool:
        """Return True when the hash distance is within the limit."""
        return self.distance <= limit


def phash_image(image: Image.Image) -> imagehash.ImageHash:
    """Compute a perceptual hash for a single image."""
    return imagehash.phash(image)


def phash_distance(observed: Image.Image, expected: Image.Image) -> int:
    """Compute the perceptual hash distance between two images."""
    return phash_image(observed) - phash_image(expected)


def phash_sequence(images: "Sequence[Image.Image]") -> list[imagehash.ImageHash]:
    """Compute perceptual hashes for a sequence of images."""
    return [phash_image(image) for image in images]


def compare_phash(
    observed: Image.Image,
    expected: Image.Image,
) -> RegressionComparison:
    """Return a comparison bundle for observed vs expected images."""
    return RegressionComparison(
        observed_hash=phash_image(observed),
        expected_hash=phash_image(expected),
    )
