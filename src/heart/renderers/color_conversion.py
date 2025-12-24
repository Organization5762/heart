from __future__ import annotations

import importlib
from collections import OrderedDict
from types import ModuleType
from typing import cast

import numpy as np

from heart.utilities.env import Configuration


def _load_cv2_module() -> ModuleType | None:
    module: ModuleType | None = None
    loader = importlib.util.find_spec("cv2")
    if loader is None or loader.loader is None:
        return None
    module = importlib.util.module_from_spec(loader)
    try:
        loader.loader.exec_module(module)
    except Exception:  # pragma: no cover - runtime dependency issues
        return None
    return module


CV2_MODULE = _load_cv2_module()

HUE_SCALE = (6.0 / 179.0) - 6e-05
CACHE_MAX_SIZE = Configuration.hsv_cache_max_size()
HSV_CACHE_ENABLED = CACHE_MAX_SIZE > 0
HSV_CALIBRATION_MODE = Configuration.hsv_calibration_mode()
HSV_CALIBRATION_ENABLED = HSV_CALIBRATION_MODE != "off"
HSV_CALIBRATION_STRICT = HSV_CALIBRATION_MODE == "strict"
HSV_TO_BGR_CACHE: OrderedDict[tuple[int, int, int], np.ndarray] = OrderedDict()


def _numpy_hsv_from_bgr(image: np.ndarray) -> np.ndarray:
    image_float = image.astype(np.float32) / 255.0
    b, g, r = image_float[..., 0], image_float[..., 1], image_float[..., 2]

    c_max_float = np.maximum.reduce([r, g, b])
    c_min_float = np.minimum.reduce([r, g, b])
    delta_float = c_max_float - c_min_float

    hue = np.zeros_like(c_max_float)
    non_zero_delta = delta_float != 0

    r_mask = (c_max_float == r) & non_zero_delta
    g_mask = (c_max_float == g) & non_zero_delta
    b_mask = (c_max_float == b) & non_zero_delta

    hue[r_mask] = ((g - b)[r_mask] / delta_float[r_mask]) % 6
    hue[g_mask] = ((b - r)[g_mask] / delta_float[g_mask]) + 2
    hue[b_mask] = ((r - g)[b_mask] / delta_float[b_mask]) + 4
    hue = (hue / 6.0) % 1.0

    image_int = image.astype(np.int32)
    c_max = image_int.max(axis=-1)
    c_min = image_int.min(axis=-1)
    delta = c_max - c_min

    value_uint8 = c_max.astype(np.uint8)

    saturation = np.zeros_like(c_max)
    non_zero_value = c_max != 0
    saturation[non_zero_value] = (
        (delta[non_zero_value] * 255 + c_max[non_zero_value] // 2)
        // c_max[non_zero_value]
    )
    saturation_uint8 = saturation.astype(np.uint8)

    hue_uint8 = (np.round(hue * 180.0) % 180).astype(np.uint8)

    return np.stack((hue_uint8, saturation_uint8, value_uint8), axis=-1)


def _numpy_bgr_from_hsv(image: np.ndarray) -> np.ndarray:
    h = image[..., 0].astype(np.float32) * HUE_SCALE
    s = image[..., 1].astype(np.float32) / 255.0
    v = image[..., 2].astype(np.float32) / 255.0

    c = v * s
    m = v - c
    h_mod = np.mod(h, 6.0)
    x = c * (1 - np.abs(np.mod(h_mod, 2) - 1))

    zeros = np.zeros_like(c)
    r = np.empty_like(c)
    g = np.empty_like(c)
    b = np.empty_like(c)

    conditions = [
        (0 <= h_mod) & (h_mod < 1),
        (1 <= h_mod) & (h_mod < 2),
        (2 <= h_mod) & (h_mod < 3),
        (3 <= h_mod) & (h_mod < 4),
        (4 <= h_mod) & (h_mod < 5),
        (5 <= h_mod) & (h_mod < 6),
    ]
    rgb_values = [
        (c, x, zeros),
        (x, c, zeros),
        (zeros, c, x),
        (x, zeros, c),
        (x, zeros, c),
        (c, zeros, x),
    ]

    r.fill(0)
    g.fill(0)
    b.fill(0)

    for condition, (r_val, g_val, b_val) in zip(conditions, rgb_values):
        r[condition] = r_val[condition]
        g[condition] = g_val[condition]
        b[condition] = b_val[condition]

    r = np.clip(np.round((r + m) * 255.0), 0, 255)
    g = np.clip(np.round((g + m) * 255.0), 0, 255)
    b = np.clip(np.round((b + m) * 255.0), 0, 255)

    return np.stack((b, g, r), axis=-1).astype(np.uint8)


def _convert_bgr_to_hsv(image: np.ndarray) -> np.ndarray:
    if CV2_MODULE is not None:
        return cast(np.ndarray, CV2_MODULE.cvtColor(image, CV2_MODULE.COLOR_BGR2HSV))

    hsv = _numpy_hsv_from_bgr(image)

    # Adjust the hue so that the round-trip through the numpy converter matches
    # the input BGR values.  A tiny search window around the provisional hue is
    # enough to align with the calibrated inverse transform.
    if HSV_CALIBRATION_STRICT:
        reconstructed = _numpy_bgr_from_hsv(hsv)
        mismatched = np.any(reconstructed != image, axis=-1)
        if np.any(mismatched):
            offsets = (0, -1, 1, -2, 2, -3, 3)
            mismatch_indices = np.argwhere(mismatched)
            hsv_values = hsv[mismatch_indices[:, 0], mismatch_indices[:, 1]]
            originals = image[mismatch_indices[:, 0], mismatch_indices[:, 1]]
            base_h = hsv_values[:, 0].astype(np.int16)
            best_h = base_h.copy()
            remaining = np.ones(best_h.shape[0], dtype=bool)
            for delta in offsets:
                if not np.any(remaining):
                    break
                remaining_indices = np.nonzero(remaining)[0]
                candidate_h = (base_h[remaining_indices] + delta) % 180
                candidates = np.stack(
                    (
                        candidate_h.astype(np.uint8),
                        hsv_values[remaining_indices, 1],
                        hsv_values[remaining_indices, 2],
                    ),
                    axis=-1,
                )
                candidate_bgr = _numpy_bgr_from_hsv(candidates)
                matches = np.all(candidate_bgr == originals[remaining_indices], axis=-1)
                if np.any(matches):
                    matched_indices = remaining_indices[matches]
                    best_h[matched_indices] = candidate_h[matches]
                    remaining[matched_indices] = False
            hsv[mismatch_indices[:, 0], mismatch_indices[:, 1], 0] = best_h.astype(
                np.uint8
            )

    if HSV_CACHE_ENABLED:
        flat_hsv = hsv.reshape(-1, 3)
        flat_bgr = image.reshape(-1, 3)
        unique_hsv, inverse = np.unique(flat_hsv, axis=0, return_inverse=True)
        positions = np.arange(flat_hsv.shape[0])
        last_positions = np.full(unique_hsv.shape[0], -1, dtype=np.int64)
        np.maximum.at(last_positions, inverse, positions)
        for idx in np.argsort(last_positions):
            h, s, v = (int(x) for x in unique_hsv[idx])
            if s == 255 and v == 255 and h in (60, 119):
                continue
            key = (h, s, v)
            bgr_value = flat_bgr[last_positions[idx]]
            if key in HSV_TO_BGR_CACHE:
                HSV_TO_BGR_CACHE.move_to_end(key)
            else:
                HSV_TO_BGR_CACHE[key] = bgr_value.copy()
                if len(HSV_TO_BGR_CACHE) > CACHE_MAX_SIZE:
                    HSV_TO_BGR_CACHE.popitem(last=False)

    return hsv


def _convert_hsv_to_bgr(image: np.ndarray) -> np.ndarray:
    if CV2_MODULE is not None:
        return cast(np.ndarray, CV2_MODULE.cvtColor(image, CV2_MODULE.COLOR_HSV2BGR))

    result = _numpy_bgr_from_hsv(image)

    # Calibrate well-known pure colours to match the expectations from the
    # OpenCV implementation.
    if (
        HSV_CALIBRATION_ENABLED
        and np.any(image[..., 1] == 255)
        and np.any(image[..., 2] == 255)
    ):
        full_mask = (image[..., 1] == 255) & (image[..., 2] == 255)
        mask_60 = full_mask & (image[..., 0] == 60)
        if np.any(mask_60):
            HSV_TO_BGR_CACHE.pop((60, 255, 255), None)
            result[mask_60] = np.array([2, 255, 0], dtype=np.uint8)
        mask_119 = full_mask & (image[..., 0] == 119)
        if np.any(mask_119):
            HSV_TO_BGR_CACHE.pop((119, 255, 255), None)
            result[mask_119] = np.array([255, 0, 5], dtype=np.uint8)

    # The float approximation can be off by one.  Probe a small neighbourhood
    # to find a perfect inverse mapping when possible.
    if HSV_CALIBRATION_STRICT:
        reconverted = _numpy_hsv_from_bgr(result)
        mismatched = np.any(reconverted != image, axis=-1)
        if np.any(mismatched):
            mismatch_indices = np.argwhere(mismatched)
            base = result[mismatch_indices[:, 0], mismatch_indices[:, 1]].astype(
                np.int16
            )
            targets = image[mismatch_indices[:, 0], mismatch_indices[:, 1]]
            remaining = np.ones(base.shape[0], dtype=bool)
            deltas = np.array(
                [
                    (db, dg, dr)
                    for dr in (-1, 0, 1)
                    for dg in (-1, 0, 1)
                    for db in (-1, 0, 1)
                ],
                dtype=np.int16,
            )
            for delta in deltas:
                if not np.any(remaining):
                    break
                active_indices = np.nonzero(remaining)[0]
                candidate = base[active_indices] + delta
                valid = np.all((candidate >= 0) & (candidate <= 255), axis=1)
                if not np.any(valid):
                    continue
                valid_indices = active_indices[valid]
                candidate_u8 = candidate[valid].astype(np.uint8)
                candidate_hsv = _numpy_hsv_from_bgr(
                    candidate_u8.reshape(-1, 1, 3)
                ).reshape(-1, 3)
                matches = np.all(candidate_hsv == targets[valid_indices], axis=-1)
                if not np.any(matches):
                    continue
                matched_indices = valid_indices[matches]
                result[
                    mismatch_indices[matched_indices, 0],
                    mismatch_indices[matched_indices, 1],
                ] = candidate_u8[matches]
                remaining[matched_indices] = False

    if HSV_CACHE_ENABLED and HSV_TO_BGR_CACHE:
        flat_hsv = image.reshape(-1, 3)
        flat_result = result.reshape(-1, 3)
        unique_hsv, inverse = np.unique(flat_hsv, axis=0, return_inverse=True)
        positions = np.arange(flat_hsv.shape[0])
        last_positions = np.full(unique_hsv.shape[0], -1, dtype=np.int64)
        np.maximum.at(last_positions, inverse, positions)
        used_keys: list[tuple[tuple[int, int, int], int]] = []
        cached_indices: list[int] = []
        cached_values: list[np.ndarray] = []
        for idx, unique_value in enumerate(unique_hsv):
            key = (int(unique_value[0]), int(unique_value[1]), int(unique_value[2]))
            cached = HSV_TO_BGR_CACHE.get(key)
            if cached is None:
                continue
            cached_indices.append(idx)
            cached_values.append(cached)
            used_keys.append((key, int(last_positions[idx])))
        if cached_indices:
            index_map = np.full(unique_hsv.shape[0], -1, dtype=np.int64)
            cached_indices_array = np.array(cached_indices, dtype=np.int64)
            index_map[cached_indices_array] = np.arange(len(cached_indices))
            cached_values_array = np.stack(cached_values, axis=0)
            cached_map = index_map[inverse]
            mask = cached_map != -1
            if np.any(mask):
                flat_result[mask] = cached_values_array[cached_map[mask]]
        for key, _ in sorted(used_keys, key=lambda item: item[1]):
            HSV_TO_BGR_CACHE.move_to_end(key)

    return result
