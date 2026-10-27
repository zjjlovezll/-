"""Station grids, their slopes and curvature, cached across contact calls.

Split out of :mod:`velch.contact`.  The rail surface at a station does not change while the
wheelset rolls through it, so these helpers hoist the interpolation out of the per-call path
and keep a small LRU window of the result.
"""
from __future__ import annotations

import math
import os
from collections import OrderedDict

import numpy as np

from .profiles import ProfileSample


_RAIL_GRID_CACHE_SIZE = 192
"""How many station grids to keep.

The run walks the profile monotonically, so a small window is enough and it keeps the
cache at a couple of megabytes instead of growing with the number of stations.
"""

_rail_grid_cache: "OrderedDict[tuple[int, float, float], tuple[np.ndarray, np.ndarray, np.ndarray, float]]" = OrderedDict()


def _build_rail_grid(rail_y: np.ndarray, rail_z: np.ndarray, rail_sample: ProfileSample,
                     grid_step_m: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Rail surface, and its slope, on a station-independent uniform axis.

    The rail geometry at a station is fixed while the wheelset moves through it, yet
    the merged-grid path re-interpolates it on every contact call -- once for the
    rail and once for the wheel, plus a sort of both node sets. Hoisting the rail
    half out of the call leaves one interpolation (the wheel) and one argmax.

    The axis spans the rail profile itself, so it does not depend on where the wheel
    currently is; each call slices the part that overlaps the wheel.
    """

    # NOTE: the axis is built from the *relative* profile coordinates.  Switching it to the
    # absolute ``rail_y`` looked like the explanation for a curved rail reading 1.46e8 N of
    # penetration, but it broke the straight frozen baseline (`ftol termination condition is
    # satisfied` in the seat) because a profile's ``y_m`` is not ordered the way this axis needs.
    # The frame question is therefore still open: see docs/CURVE_SEAT_AND_CREEP_2026-10-27.md §19.
    node = rail_sample.profile.y_m
    low = float(node[0])
    high = float(node[-1])
    span = high - low
    step = (grid_step_m if grid_step_m > 0.0 else max(2.5e-5, min(5.0e-4, span / 512.0)))
    count = max(2, int(math.floor(span / step)) + 1)
    step = span / (count - 1)
    axis = low + step * np.arange(count, dtype=float)
    axis_z = np.interp(axis, rail_y, rail_z)
    axis_slope = _grid_slope(axis_z, axis)
    return axis, axis_z, axis_slope, step


def _merge_grid(wheel_y: np.ndarray, rail_y: np.ndarray, lower: float, upper: float) -> np.ndarray:
    """Sorted union of the two lateral grids inside [lower, upper].

    Identical values to ``np.unique(np.concatenate(...))`` but without the
    hashing path: both sources are already increasing, so a sort plus an
    adjacency mask reproduces the same ascending, duplicate-free array.
    """
    parts = [np.array([lower, upper])]
    inside = wheel_y[(wheel_y > lower) & (wheel_y < upper)]
    if inside.size:
        parts.append(inside)
    inside = rail_y[(rail_y > lower) & (rail_y < upper)]
    if inside.size:
        parts.append(inside)
    merged = np.sort(np.concatenate(parts)) if len(parts) > 1 else parts[0]
    if merged.size > 1:
        keep = np.empty(merged.size, dtype=bool)
        keep[0] = True
        keep[1:] = merged[1:] != merged[:-1]
        merged = merged[keep]
    return merged


def _grid_slope(z: np.ndarray, x: np.ndarray) -> np.ndarray:
    """``np.gradient(z, x, edge_order=1)`` written out for the hot path."""
    n = z.size
    slope = np.empty(n, dtype=float)
    if n == 2:
        slope[0] = slope[1] = (z[1] - z[0]) / (x[1] - x[0])
        return slope
    slope[0] = (z[1] - z[0]) / (x[1] - x[0])
    slope[-1] = (z[-1] - z[-2]) / (x[-1] - x[-2])
    slope[1:-1] = (z[2:] - z[:-2]) / (x[2:] - x[:-2])
    return slope


def _grid_curvature(z: np.ndarray, x: np.ndarray) -> np.ndarray:
    """Second derivative of ``z(x)`` on the merged grid, for the ``grid_stencil`` policy.

    Two extra vectorised passes over arrays the search already holds, in place of
    two least-squares window fits over the raw node lists (about 50 µs of a
    108 µs geometry call). Same meaning as ``2 * quadratic[0]`` from
    :func:`_window_quadratic`, different smoothing length: one grid step here,
    the ±half_span window there.
    """
    n = z.size
    curvature = np.empty(n, dtype=float)
    if n < 3:
        curvature.fill(0.0)
        return curvature
    width = 0.5 * (x[2:] - x[:-2])
    curvature[1:-1] = 2.0 * (z[2:] - 2.0 * z[1:-1] + z[:-2]) / (width * width)
    curvature[0] = curvature[1]
    curvature[-1] = curvature[-2]
    return curvature


_RAIL_SLOPE_CACHE: "OrderedDict[tuple, np.ndarray]" = OrderedDict()
_RAIL_SLOPE_CACHE_SIZE = 512
# Off by default: measured on ``case_frog_N_strip05`` (101 samples, 8 contacts) the forces
# came back bitwise identical (max|dN| = 0.000e+00 N) but the wall clock did not move --
# 17.38 s fresh versus 17.67 s with the table, i.e. 0.98x.  Hashing a 2144-node profile
# costs about what the central difference it replaces costs, so the saving cancels.  It
# becomes profitable only once the key is the station index the caller already holds
# (no hash at all); until then the exact-but-inert path stays behind the switch.
#   VELCH_RAIL_SLOPE_TABLE=1   force it on (forces are unchanged)
RAIL_SLOPE_TABLE = os.environ.get("VELCH_RAIL_SLOPE_TABLE", "0") == "1"


def _rail_node_slopes(rail_y: np.ndarray, rail_z: np.ndarray,
                      surface_key) -> np.ndarray | None:
    """``dz/dy`` at the rail nodes, cached per station.

    The merged contact grid is dominated by rail nodes -- about 2000 of the 2144 points
    on a turnout station -- and the slope there is the same central difference no matter
    which axle or side is asking, so recomputing it once per contact call throws away the
    number of contacts per step.  Keyed on the station identity plus a fingerprint of the
    sampled profile, never on ``id``: ``ProfileSeries`` may hand out a fresh
    ``GraphProfile`` per sample, and a stale key here is what once turned a 170 kN peak
    into 1447 kN.

    Substituting the interpolated node slopes for a fresh difference on the merged grid
    is exact at rail nodes and is the same linear blend at the wheel nodes inserted
    between them, which is why the A/B run is asked for equality rather than closeness.
    """
    if not RAIL_SLOPE_TABLE or rail_y.size < 3:
        return None
    # Content fingerprint, not ``id`` and not the station label alone: ``ProfileSeries``
    # may hand out a fresh ``GraphProfile`` per sample, and two stations whose sampled
    # nodes hash the same are the same profile to within a floating-point bit -- which is
    # exactly the reuse this table is allowed to make.  The full-array hash costs about
    # a microsecond and buys immunity to the stale-key failure that once produced
    # 1447 kN; a three-point fingerprint is not enough to prove equality.
    key = (rail_y.size, hash(rail_z.tobytes()))
    cached = _RAIL_SLOPE_CACHE.get(key)
    if cached is not None:
        _RAIL_SLOPE_CACHE.move_to_end(key)
        return cached
    slopes = _grid_slope(rail_z, rail_y)
    _RAIL_SLOPE_CACHE[key] = slopes
    _RAIL_SLOPE_CACHE.move_to_end(key)
    while len(_RAIL_SLOPE_CACHE) > _RAIL_SLOPE_CACHE_SIZE:
        _RAIL_SLOPE_CACHE.popitem(last=False)
    return slopes
