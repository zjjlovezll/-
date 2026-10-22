"""Contact map: turn the per-step geometry search into an interpolation.

Why a map and not a per-station cache
-------------------------------------
``ProfileSeries.sample`` blends the two stations that bracket ``s``, so every internal
step produces a *distinct* profile and any cache keyed on the station or on the profile
content never hits: an A/B on ``case_frog_N_strip05`` gave bitwise-identical forces
(``max|dN| = 0.000e+00 N``) and 0.98x.  The geometry therefore has to be precomputed as a
function of the *relative pose*, where the inputs repeat across steps, and each step then
becomes an interpolation instead of a search.

Structure
---------
``build_map`` evaluates a user-supplied contact function on a rectangular grid of
``(lateral offset, height offset)`` and stores the penetration and both normal
components.  ``ContactMap.evaluate`` returns the same tuple by trilinear interpolation in
the pose space.  The module knows nothing about Velch's profile objects: the caller hands
in a closure, which keeps this file independent of the solver and testable on a geometry
with a closed-form answer.

Acceptance gates (must all pass before the map may be enabled)
-------------------------------------------------------------
``rms_delta <= 1.0 um``, ``max_delta <= 5.0 um``, ``max_shift <= 20.0 um`` (contact
lateral position), ``peak_force <= 0.5 %``, and the per-lookup cost must be far below one
direct geometry call.

Run ``python -X utf8 -m velch.contact_map`` for the self-test: two circular arcs
(``R_w = 0.430 m`` tread, ``R_r = 0.300 m`` crown), whose contact is found to 20001-point
resolution as the reference, against a 33 x 41 map.  A circular pair is the exact
wheel-on-rail idealisation, so the interpolation error measured here is the error the
real profile pairs would see on their smooth stretches -- not on a sharp flange groove,
where the gates are known to be violated and the map must fall back to a direct search.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

import numpy as np

GATE_RMS_DELTA_M = 1.0e-6
GATE_MAX_DELTA_M = 5.0e-6
GATE_MAX_SHIFT_M = 20.0e-6
GATE_PEAK_FORCE_REL = 0.005


@dataclass(frozen=True)
class ContactMap:
    """Sampled contact pose response for one rail body, in the rail's own frame."""

    offsets_m: np.ndarray      # ascending lateral wheel offsets
    heights_m: np.ndarray      # ascending height offsets of the wheel centre
    penetration_m: np.ndarray  # (offset, height)
    normal_y: np.ndarray       # (offset, height), unit vector components
    normal_z: np.ndarray
    contact_y_m: np.ndarray    # absolute lateral position of the contact point, rail frame
    source: str = "velch_contact_map_v1"

    def evaluate(self, offset_m: float, height_m: float) -> tuple[float, float, float, float]:
        """Return ``(penetration_m, normal_y, normal_z, contact_y_m)`` by trilinear blend."""
        o = np.clip(offset_m, self.offsets_m[0], self.offsets_m[-1])
        h = np.clip(height_m, self.heights_m[0], self.heights_m[-1])
        io = int(np.searchsorted(self.offsets_m, o, side="right") - 1)
        ih = int(np.searchsorted(self.heights_m, h, side="right") - 1)
        io = min(max(io, 0), self.offsets_m.size - 2)
        ih = min(max(ih, 0), self.heights_m.size - 2)
        fo = (o - self.offsets_m[io]) / (self.offsets_m[io + 1] - self.offsets_m[io])
        fh = (h - self.heights_m[ih]) / (self.heights_m[ih + 1] - self.heights_m[ih])

        def blend(grid: np.ndarray) -> float:
            a = grid[io, ih] * (1.0 - fo) + grid[io + 1, ih] * fo
            b = grid[io, ih + 1] * (1.0 - fo) + grid[io + 1, ih + 1] * fo
            return a * (1.0 - fh) + b * fh

        return (blend(self.penetration_m), blend(self.normal_y),
                blend(self.normal_z), blend(self.contact_y_m))


def build_map(contact, offsets_m, heights_m, *, source: str = "velch_contact_map_v1") -> ContactMap:
    """Sample ``contact(offset_m, height_m) -> (pen, ny, nz, y_contact)`` on a grid."""
    offsets = np.asarray(offsets_m, dtype=float)
    heights = np.asarray(heights_m, dtype=float)
    shape = (offsets.size, heights.size)
    penetration = np.zeros(shape)
    normal_y = np.zeros(shape)
    normal_z = np.zeros(shape)
    contact_y = np.zeros(shape)
    for i, offset in enumerate(offsets):
        for j, height in enumerate(heights):
            pen, ny, nz, yc = contact(float(offset), float(height))
            penetration[i, j] = pen
            normal_y[i, j] = ny
            normal_z[i, j] = nz
            contact_y[i, j] = yc
    return ContactMap(offsets, heights, penetration, normal_y, normal_z, contact_y, source)


# --------------------------------------------------------------------------- self-test
def _two_arc_contact(offset_m: float, height_m: float) -> tuple[float, float, float, float]:
    """Wheel tread circle on a rail crown circle, solved to 20001-point resolution."""
    r_wheel = 0.430
    r_rail = 0.300
    y = np.linspace(-0.060, 0.060, 20001)
    # A rail crown is convex *up*: highest on the reference line and falling away, which is
    # ``sqrt - R`` and not ``R - sqrt`` -- the latter is a valley, and with a valley the
    # deepest relative approach sits at the window edge for every pose, so the contact
    # position was pinned at +-60 mm and the shift gate read 119 mm against a number that
    # was itself an artefact.
    z_rail = np.sqrt(np.maximum(r_rail * r_rail - y * y, 0.0)) - r_rail
    dy = y - offset_m
    z_wheel = height_m + r_wheel - np.sqrt(np.maximum(r_wheel * r_wheel - dy * dy, 0.0))
    delta = z_rail - z_wheel
    k = int(np.argmax(delta))
    if delta[k] <= 0.0:
        # No penetration: the contact position is undefined, so report the closest
        # approach instead of the search window's edge.  An edge pick (y = +-60 mm) is
        # what made the first version of the shift gate read 119 mm -- the gate was
        # measuring an artefact of where the window ends, not an interpolation error.
        k = int(np.argmin(np.abs(delta)))
        return 0.0, 0.0, -1.0, float(y[k])
    slope_rail = -y[k] / np.sqrt(max(r_rail * r_rail - y[k] * y[k], 1e-12))
    slope_wheel = -dy[k] / np.sqrt(max(r_wheel * r_wheel - dy[k] * dy[k], 1e-12))
    gy, gz = slope_rail - slope_wheel, -1.0
    norm = math.hypot(gy, gz)
    return float(max(delta[k], 0.0)), gy / norm, gz / norm, float(y[k])


def _self_test() -> int:
    offsets = np.linspace(-0.008, 0.008, 33)
    heights = np.linspace(-0.00040, 0.00040, 41)
    started = time.perf_counter()
    contact_map = build_map(_two_arc_contact, offsets, heights)
    build_s = time.perf_counter() - started

    rng = np.random.default_rng(20261021)
    n = 2000
    test_offsets = rng.uniform(offsets[0], offsets[-1], n)
    test_heights = rng.uniform(heights[0], heights[-1], n)
    direct_pen = np.empty(n)
    map_pen = np.empty(n)
    direct_y = np.empty(n)
    map_y = np.empty(n)
    for i in range(n):
        pen, _ny, _nz, yc = _two_arc_contact(float(test_offsets[i]), float(test_heights[i]))
        direct_pen[i] = pen
        direct_y[i] = yc
        mpen, _mny, _mnz, myc = contact_map.evaluate(float(test_offsets[i]),
                                                     float(test_heights[i]))
        map_pen[i] = mpen
        map_y[i] = myc

    delta = map_pen - direct_pen
    rms = float(np.sqrt(np.mean(delta * delta)))
    worst = float(np.max(np.abs(delta)))
    # The contact position only carries meaning where there is contact; outside it both
    # sides report a closest approach, whose lateral position is a property of the window.
    touching = direct_pen > 0.0
    shift = float(np.max(np.abs(map_y[touching] - direct_y[touching]))) if touching.any() else 0.0
    # Hertz with a fixed combined modulus and the mean penetration of the sample.
    c = 2.148e10
    f_direct = c * np.power(np.maximum(direct_pen, 0.0), 1.5)
    f_map = c * np.power(np.maximum(map_pen, 0.0), 1.5)
    peak_rel = float(abs(f_map.max() - f_direct.max()) / max(f_direct.max(), 1e-9))

    started = time.perf_counter()
    for i in range(2000):
        contact_map.evaluate(float(test_offsets[i]), float(test_heights[i]))
    lookup_us = (time.perf_counter() - started) / 2000.0 * 1e6
    started = time.perf_counter()
    for i in range(200):
        _two_arc_contact(float(test_offsets[i]), float(test_heights[i]))
    direct_us = (time.perf_counter() - started) / 200.0 * 1e6

    gates = {
        "rms_delta": (rms, GATE_RMS_DELTA_M, rms <= GATE_RMS_DELTA_M),
        "max_delta": (worst, GATE_MAX_DELTA_M, worst <= GATE_MAX_DELTA_M),
        "max_shift": (shift, GATE_MAX_SHIFT_M, shift <= GATE_MAX_SHIFT_M),
        "peak_force_rel": (peak_rel, GATE_PEAK_FORCE_REL, peak_rel <= GATE_PEAK_FORCE_REL),
    }
    print(f"map {contact_map.offsets_m.size}x{contact_map.heights_m.size} "
          f"build {build_s:.2f} s, lookup {lookup_us:.2f} us, direct {direct_us:.1f} us "
          f"({direct_us / lookup_us:.0f}x)")
    for name, (value, limit, ok) in gates.items():
        print(f"  {name:15s} {value:.3e} <= {limit:.1e}  {'PASS' if ok else 'FAIL'}")
    return 0 if all(ok for _v, _l, ok in gates.values()) else 1


if __name__ == "__main__":
    raise SystemExit(_self_test())
