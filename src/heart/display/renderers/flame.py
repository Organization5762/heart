import pygame.transform as pgt
import numpy as np
import pygame
import pygame.surfarray as sarr


# I took this shader https://www.shadertoy.com/view/mtjyzG and asked chat to convert it to python

def _step(a, threshold):
    return (a >= threshold).astype(np.float32)  # 0. or 1.


def _mix(a, b, alpha):
    """
    GLSL‑style mix().  Works with
      • scalar alpha   – single blend factor
      • 2‑D   alpha    – greyscale mask, auto‑expanded to (H,W,1)
      • 3‑D   alpha    – per‑channel alpha (already shape‑compatible)
    """
    if np.isscalar(alpha):  # plain float → broadcast OK
        return a * (1.0 - alpha) + b * alpha

    alpha = np.asarray(alpha, dtype=np.float32)
    if alpha.ndim == a.ndim - 1:  # (H,W) → (H,W,1)
        alpha = alpha[..., None]

    return a * (1.0 - alpha) + b * alpha


def _smoothstep(edge0, edge1, x):
    # identical to GLSL smoothstep
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _noise21(ix, iy):
    """
    32‑bit LCG / hash implemented with 64‑bit intermediates so it can't overflow.
    Returns deterministic [0,1] noise for every integer coord pair.
    """
    ix = ix.astype(np.int64, copy=False)  # promote once, keep view‑only
    iy = iy.astype(np.int64, copy=False)

    w, s = 32, 16  # bit‑width & rotation (same as shader)

    # --- the exact hash chain from the original GLSL ---
    a = (ix * 3284157443) & 0xFFFFFFFF
    b = (iy ^ ((a << s) | (a >> (w - s)))) & 0xFFFFFFFF
    b = (b * 1911520717) & 0xFFFFFFFF
    a = (a ^ ((b << s) | (b >> (w - s)))) & 0xFFFFFFFF
    a = (a * 2048419325) & 0xFFFFFFFF

    # convert to float in [0,1]
    rand = a.astype(np.float32) * (3.14159265 / 2147483647.0)
    return np.cos(rand) * 0.5 + 0.5


def _noise22(ix, iy):
    # simplified, good enough for cell jitter
    n = np.sin(ix * 138.546 + iy * 78.233) * 43758.5453
    n2 = np.sin(ix * 12.9898 + iy * 4.1414) * 12543.2451
    return np.modf(np.stack((n, n2), axis=-1))[0]  # fract()


def _smooth_noise(u, v):
    # u,v are fractional; iv, iu integer
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
    t = _mix(tl, tr, fu)
    b = _mix(bl, br, fu)
    return _mix(b, t, fv)


def _layer_noise(u, v):
    res = np.zeros_like(u, dtype=np.float32)
    amp = 1.0
    freq = 10.0
    norm = 0.0
    for _ in range(4):
        res += _smooth_noise(u * freq, v * freq) * amp
        norm += amp
        amp *= 0.5
        freq *= 2.0
    return res / norm


def _voronoi(u, v, t):
    iu = np.floor(u).astype(np.int32)
    iv = np.floor(v).astype(np.int32)
    fu = u - iu - 0.5
    fv = v - iv - 0.5
    min_d = np.full_like(u, 100.0, dtype=np.float32)

    for ox in (-1, 0, 1):
        for oy in (-1, 0, 1):
            jitter = _noise22(iu + ox, iv + oy)  # 2‑vector
            px = ox + np.sin(jitter[..., 0] * t) * 0.5
            py = oy + np.sin(jitter[..., 1] * t) * 0.5
            d = np.sqrt((fu - px) ** 2 + (fv - py) ** 2)
            min_d = np.minimum(min_d, d)
    return _smoothstep(0.0, 1.0, min_d)


def _flame_layer(u, v, t, col_rgb, thr):
    ln = _layer_noise(u + 0.25 * t, v - 0.5 * t)
    vn = _voronoi(u * 3.0, v * 3.0 - 0.25 * t, t)
    res = ln * _mix(ln, vn, 0.7)
    res = _smoothstep(res, 0.0, 1.0 - v)  # fade downward (inverted v)
    res = _step(res, thr)  # binary mask
    return res[..., None] * col_rgb  # shape (...,3)

class FlameGenerator:
    """
    Produces a 64×H animated flame Surface.
    """

    _LAYERS = [
        ((0.769, 0.153, 0.153), 0.001),
        ((0.886, 0.345, 0.133), 0.1),
        ((0.914, 0.475, 0.102), 0.5),
        ((0.945, 0.604, 0.067), 0.8),
        ((0.973, 0.729, 0.035), 0.9),
        ((1.000, 0.900, 0.600), 0.99),
    ]

    def __init__(self, width=64, height=16):
        self.w = width
        self.h = height
        # pre‑compute static coordinate grids
        y, x = np.indices((height, width), dtype=np.float32)
        # shader‑style normalised UV
        self.u = (x - 0.5 * width) / height
        self.v0 = (y - 0.5 * height) / height + 0.5
        # pixelate to 1/64 just like GLSL
        snap = 1.0 / 64.0
        self.u -= np.mod(self.u, snap)
        self.v0 -= np.mod(self.v0, snap)

    def surface(self, t: float, side: str = "bottom") -> pygame.Surface:
        """
        side = "bottom" | "top" | "left" | "right"
        """
        # -------------- generate the canonical strip (bottom → up) -------------
        v = self.v0.copy()
        u = self.u
        col = np.zeros((self.h, self.w, 3), dtype=np.float32)
        for rgb, thr in self._LAYERS:
            layer = _flame_layer(u, v, t, np.array(rgb, np.float32), thr)
            col = _mix(col, layer, layer[..., 0][..., None])

        surf = pygame.Surface((self.w, self.h))
        surf.set_colorkey((0, 0, 0))
        sarr.blit_array(
            surf, (np.clip(col * 255, 0, 255)).astype(np.uint8).swapaxes(0, 1)
        )

        # -------------- orient the strip for the requested side ----------------
        match side:
            case "bottom":  # already correct
                return surf

            case "top":  # upside‑down
                return pgt.flip(surf, False, True)

            case "left":  # 90° clockwise → base on the left edge
                return pgt.rotate(surf, -90)

            case "right":  # 90° counter‑clockwise → base on the right edge
                return pgt.rotate(surf, 90)

            case _:
                raise ValueError("side must be bottom|top|left|right")
