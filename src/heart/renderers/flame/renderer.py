from __future__ import annotations

import numpy as np
import pygame
import pygame.surfarray as sarr
import pygame.transform as pgt
import reactivex
from pygame import Surface

from heart import DeviceDisplayMode
from heart.device import Orientation
from heart.peripheral.core.manager import PeripheralManager
from heart.renderers import StatefulBaseRenderer
from heart.renderers.flame.provider import FlameStateProvider
from heart.renderers.flame.state import FlameState

DEFAULT_FLAME_WIDTH = 64
DEFAULT_FLAME_HEIGHT = 16
DEFAULT_FLAME_SIDE = "bottom"

# ------------------------------------------------------------------------------------
#  Utility helpers
# ------------------------------------------------------------------------------------
def _step(a, threshold):
    """Return a binary mask where a >= threshold (float32)."""
    # `astype(copy=False)` re-uses the original buffer when possible
    return (a >= threshold).astype(np.float32, copy=False)


def _mix(a, b, alpha):
    """GLSL-style mix().

    Handles scalar / greyscale / per-channel alpha.

    """
    if np.isscalar(alpha):
        return a * (1.0 - alpha) + b * alpha

    alpha = np.asarray(alpha, dtype=np.float32)
    if alpha.ndim == a.ndim - 1:  # (H,W) → (H,W,1)
        alpha = alpha[..., None]

    return a * (1.0 - alpha) + b * alpha


def _smoothstep(edge0, edge1, x):
    """Classic smoothstep."""
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# ------------------------------------------------------------------------------------
#  Noise helpers (unchanged – already nicely vectorised)
# ------------------------------------------------------------------------------------
def _noise21(ix, iy):
    """Hash → scalar noise in [0,1].

    Guaranteed deterministic.

    """
    ix = ix.astype(np.int64, copy=False)
    iy = iy.astype(np.int64, copy=False)

    w, s = 32, 16
    a = (ix * 3284157443) & 0xFFFFFFFF
    b = (iy ^ ((a << s) | (a >> (w - s)))) & 0xFFFFFFFF
    b = (b * 1911520717) & 0xFFFFFFFF
    a = (a ^ ((b << s) | (b >> (w - s)))) & 0xFFFFFFFF
    a = (a * 2048419325) & 0xFFFFFFFF

    rand = a.astype(np.float32) * (3.14159265 / 2147483647.0)
    return np.cos(rand) * 0.5 + 0.5


def _noise22(ix, iy):
    """Cheap 2-vector noise – good enough for Voronoi jitter."""
    n1 = np.sin(ix * 138.546 + iy * 78.233) * 43758.5453
    n2 = np.sin(ix * 12.9898 + iy * 4.1414) * 12543.2451
    return np.modf(np.stack((n1, n2), axis=-1))[0]  # fract()


# ------------------------------------------------------------------------------------
#  Layered noise / Voronoi helpers
# ------------------------------------------------------------------------------------
def _smooth_noise(u, v):
    """Smooth (Perlin-style) noise."""
    iu = np.floor(u).astype(np.int32)
    iv = np.floor(v).astype(np.int32)
    fu = u - iu
    fv = v - iv
    fu = fu * fu * (3.0 - 2.0 * fu)
    fv = fv * fv * (3.0 - 2.0 * fv)

    tl = _noise21(iu, iv + 1)
    bl = _noise21(iu, iv)
    tr = _noise21(iu + 1, iv + 1)
    br = _noise21(iu + 1, iv)
    return _mix(_mix(bl, br, fu), _mix(tl, tr, fu), fv)


def _layer_noise(u, v):
    """4-octave FBM."""
    res = np.zeros_like(u, dtype=np.float32)
    amp, freq, norm = 1.0, 10.0, 0.0
    for _ in range(4):
        res += _smooth_noise(u * freq, v * freq) * amp
        norm += amp
        amp *= 0.5
        freq *= 2.0
    return res / norm


def _voronoi(u, v, t):
    """Vectorised Voronoi – no Python loops over pixels."""
    iu = np.floor(u).astype(np.int32)
    iv = np.floor(v).astype(np.int32)

    fu = u - iu - 0.5
    fv = v - iv - 0.5

    # Offsets -1,0,1  → shape (3,3,1,1) ready for broadcasting
    offsets = np.array([-1, 0, 1], dtype=np.int32)
    ox, oy = np.meshgrid(offsets, offsets, indexing="ij")
    ox = ox[..., None, None]
    oy = oy[..., None, None]

    jitter = _noise22(iu + ox, iv + oy)  # (3,3,H,W,2)
    px = ox + np.sin(jitter[..., 0] * t) * 0.5
    py = oy + np.sin(jitter[..., 1] * t) * 0.5

    d = np.sqrt((fu - px) ** 2 + (fv - py) ** 2)  # (3,3,H,W)
    min_d = d.min(axis=(0, 1))  # (H,W)
    return _smoothstep(0.0, 1.0, min_d)


def _flame_layer(u, v, t, col_rgb, thr):
    """Legacy helper kept for external callers.

    Internally the generator now pre-computes expensive pieces once per frame.

    """
    ln = _layer_noise(u + 0.125 * t, v - 0.25 * t)  # Half speed (0.25→0.125, 0.5→0.25)
    vn = _voronoi(u * 3.0, v * 3.0 - 0.125 * t, t)  # Half speed (0.25→0.125)
    res = ln * _mix(ln, vn, 0.7)
    res = _smoothstep(res, 0.0, 1.0 - v)  # fade downward
    res = _step(res, thr)  # binary mask
    return res[..., None] * col_rgb  # (H,W,3)


# ------------------------------------------------------------------------------------
#  Public generator class
# ------------------------------------------------------------------------------------
class FlameGenerator:
    """Produces a 64×H animated flame Surface."""

    _LAYERS = [
        ((0.769, 0.153, 0.153), 0.001),
        ((0.886, 0.345, 0.133), 0.100),
        ((0.914, 0.475, 0.102), 0.500),
        ((0.945, 0.604, 0.067), 0.800),
        ((0.973, 0.729, 0.035), 0.900),
        ((1.000, 0.900, 0.600), 0.990),
    ]

    def __init__(
        self,
        width: int = DEFAULT_FLAME_WIDTH,
        height: int = DEFAULT_FLAME_HEIGHT,
    ):
        self.w, self.h = width, height

        # Static UV grids (pixelated to 1/64 like the shader)
        y, x = np.indices((height, width), dtype=np.float32)
        self.u = (x - 0.5 * width) / height
        self.v0 = (y - 0.5 * height) / height + 0.5
        snap = 1.0 / 64.0
        self.u -= np.mod(self.u, snap)
        self.v0 -= np.mod(self.v0, snap)

        # Pre-compute arrays & buffers to avoid per-frame allocations
        self._layer_rgbs = np.array([rgb for rgb, _ in self._LAYERS], dtype=np.float32)
        self._layer_thrs = np.array([thr for _, thr in self._LAYERS], dtype=np.float32)
        self._col_buf = np.empty((height, width, 3), dtype=np.float32)
        self._surf = pygame.Surface((self.w, self.h))
        self._surf.set_colorkey((0, 0, 0))

    # -------------------------------------------------------------------------
    #  Public API
    # -------------------------------------------------------------------------
    def surface(self, t: float, side: str = DEFAULT_FLAME_SIDE) -> pygame.Surface:
        """Generate the flame strip for the given time `t`.

        side ∈ {"bottom","top","left","right"} – controls orientation.

        """
        u, v = self.u, self.v0  # aliases: no copies
        col = self._col_buf
        col.fill(0.0)  # reuse buffer instead of allocating

        # ------------------------------------------------------------------
        # 1) EXPENSIVE PART: evaluate once per frame
        # ------------------------------------------------------------------
        ln = _layer_noise(
            u + 0.125 * t, v - 0.25 * t
        )  # Half speed (0.25→0.125, 0.5→0.25)
        vn = _voronoi(u * 3.0, v * 3.0 - 0.125 * t, t)  # Half speed (0.25→0.125)
        base = ln * _mix(ln, vn, 0.7)
        base = _smoothstep(base, 0.0, 1.0 - v)  # fade downward

        # ------------------------------------------------------------------
        # 2) Threshold / colour merge (cheap; 6 iterations)
        # ------------------------------------------------------------------
        for rgb, thr in zip(self._layer_rgbs, self._layer_thrs):
            alpha = _step(base, thr)[..., None]  # (H,W,1) float mask
            col += (rgb - col) * alpha  # GLSL-style mix

        # ------------------------------------------------------------------
        # 3) Copy pixels → pygame.Surface (in-place; no extra Surface)
        # ------------------------------------------------------------------
        rgb8 = np.clip(col * 255.0, 0, 255).astype(np.uint8)
        surfpx = sarr.pixels3d(self._surf)  # (W,H,3) view
        surfpx[...] = rgb8.swapaxes(0, 1)  # transpose H/W
        del surfpx  # unlock the Surface

        # ----------------------------- orientation ----------------------------
        if side == "bottom":
            return self._surf
        if side == "top":
            return pgt.flip(self._surf, False, True)
        if side == "left":
            return pgt.rotate(self._surf, -90)
        if side == "right":
            return pgt.rotate(self._surf, 90)

        raise ValueError("side must be 'bottom', 'top', 'left' or 'right'")


class FlameRenderer(StatefulBaseRenderer[FlameState]):
    """Display animated flames on all four sides of the screen."""

    def __init__(self, provider: FlameStateProvider | None = None) -> None:
        self._provider = provider or FlameStateProvider()
        super().__init__(builder=self._provider)
        self.device_display_mode = DeviceDisplayMode.MIRRORED
        self._flame_generator = FlameGenerator(64, 16)

    def state_observable(
        self, peripheral_manager: PeripheralManager
    ) -> reactivex.Observable[FlameState]:
        return self._provider.observable(peripheral_manager)

    def real_process(
        self,
        window: Surface,
        clock: pygame.time.Clock,
        orientation: Orientation,
    ) -> None:
        state = self.state
        t = state.time_seconds

        base_flame = self._flame_generator.surface(t, "bottom")

        flame_surfaces = {
            "bottom": base_flame,
            "top": pgt.flip(base_flame.copy(), False, True),
            "left": pgt.rotate(base_flame.copy(), -90),
            "right": pgt.rotate(base_flame.copy(), 90),
        }

        window_width, window_height = window.get_size()

        window.blit(flame_surfaces["bottom"], (0, window_height - 16))
        window.blit(flame_surfaces["top"], (0, 0))
        window.blit(flame_surfaces["left"], (0, 0))
        window.blit(flame_surfaces["right"], (window_width - 16, 0))
