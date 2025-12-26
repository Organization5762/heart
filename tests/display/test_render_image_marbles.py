"""Exercise RenderImage reactive outputs with marble diagrams."""

from __future__ import annotations

from dataclasses import dataclass

import pygame
import pytest
import reactivex
from reactivex import operators as ops
from reactivex.testing.marbles import marbles_testing

from heart.assets.loader import Loader
from heart.renderers.image.provider import RenderImageStateProvider
from heart.runtime.frame_exporter import FrameExporter
from heart.utilities.env import FrameExportStrategy


@dataclass(frozen=True)
class _StubManager:
    window: reactivex.Observable[pygame.Surface | None]


class TestRenderImageMarbleOutputs:
    """Validate marbled window updates produce correct output images for reactive rendering."""

    @pytest.mark.parametrize(
        ("sizes", "expected_sizes"),
        [
            ([(2, 2), (4, 4), (4, 4)], [(2, 2), (4, 4)]),
            ([(1, 3), (1, 3), (5, 2)], [(1, 3), (5, 2)]),
        ],
        ids=["dedupe-repeated-size", "dedupe-non-square"],
    )
    def test_marble_stream_scales_images_to_window_sizes(
        self,
        monkeypatch: pytest.MonkeyPatch,
        sizes: list[tuple[int, int]],
        expected_sizes: list[tuple[int, int]],
    ) -> None:
        """Confirm marble-timed window sizes emit scaled images so render streams stay deterministic."""

        base_surface = pygame.Surface((2, 2), pygame.SRCALPHA)
        base_surface.fill((10, 20, 30, 255))
        monkeypatch.setattr(Loader, "load", lambda _: base_surface)
        pygame.display.set_mode((1, 1))

        marble_labels = ["a", "b", "c"]
        window_values = {
            label: pygame.Surface(size, pygame.SRCALPHA)
            for label, size in zip(marble_labels, sizes, strict=True)
        }
        provider = RenderImageStateProvider(image_file="fixture.png")
        exporter = FrameExporter(
            strategy_provider=lambda: FrameExportStrategy.ARRAY
        )

        with marbles_testing() as (start, _cold, hot, _exp):
            window_stream = hot("-a-b-c-|", window_values)
            manager = _StubManager(window=window_stream)
            image_stream = provider.observable(manager).pipe(
                ops.map(
                    lambda state: pygame.transform.scale(
                        state.base_image, state.window_size
                    )
                ),
                ops.map(exporter.export),
            )
            records = start(image_stream)

        images = [
            (record.value.value.size, record.value.value.getpixel((0, 0)))
            for record in records
            if record.value.kind == "N"
        ]

        assert images == [(size, (10, 20, 30)) for size in expected_sizes]

    @pytest.mark.parametrize(
        ("sizes", "expected_sizes"),
        [
            ([(1, 1), (3, 2), (3, 2)], [(1, 1), (3, 2)]),
            ([(4, 1), (4, 1), (2, 4)], [(4, 1), (2, 4)]),
        ],
        ids=["array-buffer-match-rect", "array-buffer-match-flip"],
    )
    def test_marble_stream_exports_consistent_images_across_strategies(
        self,
        monkeypatch: pytest.MonkeyPatch,
        sizes: list[tuple[int, int]],
        expected_sizes: list[tuple[int, int]],
    ) -> None:
        """Check marbled exports align across array/buffer strategies to keep outputs stable."""

        base_surface = pygame.Surface((1, 1), pygame.SRCALPHA)
        base_surface.fill((100, 150, 200, 255))
        monkeypatch.setattr(Loader, "load", lambda _: base_surface)
        pygame.display.set_mode((1, 1))

        marble_labels = ["a", "b", "c"]
        window_values = {
            label: pygame.Surface(size, pygame.SRCALPHA)
            for label, size in zip(marble_labels, sizes, strict=True)
        }
        provider = RenderImageStateProvider(image_file="fixture.png")
        array_exporter = FrameExporter(
            strategy_provider=lambda: FrameExportStrategy.ARRAY
        )
        buffer_exporter = FrameExporter(
            strategy_provider=lambda: FrameExportStrategy.BUFFER
        )

        with marbles_testing() as (start, _cold, hot, _exp):
            window_stream = hot("-a-b-c-|", window_values)
            manager = _StubManager(window=window_stream)
            image_stream = provider.observable(manager).pipe(
                ops.map(
                    lambda state: pygame.transform.scale(
                        state.base_image, state.window_size
                    )
                ),
                ops.map(
                    lambda surface: (
                        array_exporter.export(surface),
                        buffer_exporter.export(surface),
                    )
                ),
            )
            records = start(image_stream)

        images = [
            (
                record.value.value[0].size,
                record.value.value[0].convert("RGBA").getpixel((0, 0)),
                record.value.value[1].size,
                record.value.value[1].convert("RGBA").getpixel((0, 0)),
            )
            for record in records
            if record.value.kind == "N"
        ]

        expected = [
            (size, (100, 150, 200, 255), size, (100, 150, 200, 255))
            for size in expected_sizes
        ]

        assert images == expected
