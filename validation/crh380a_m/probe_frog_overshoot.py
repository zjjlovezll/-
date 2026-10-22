"""Probe: does the 499 um relaxed spline piece sit on the contact point?

The segmented report showed the frog residual (293 um) is stable when the grid is
refined, so it is a *representation* difference, not grid quantisation. The band's
worst relaxed overshoot (499 um) is the same order, which suggests one of the pieces
that could not meet the 2 um gate straddles the contact. This probe answers it
directly: for the worst frog sample it prints the contacting piece of each band, its
own fit residual, and whether it was relaxed.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BASE / "src"))

import os  # noqa: E402

os.chdir(BASE)
sys.argv = [sys.argv[0], "case_I_wing.json"]

_spec = importlib.util.spec_from_file_location(
    "report_seg", Path(__file__).with_name("report_spline_segmented.py"))
rep = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rep)

from velch.contact import _absolute_arrays  # noqa: E402
from velch.contact_geometry import fit_segmented, swept_contact  # noqa: E402
from velch.vehicle import load_vehicle_case  # noqa: E402


def piece_of(band, y):
    """Index of the piece that owns ``y`` and whether that piece was relaxed."""
    index = int(np.searchsorted(np.asarray(band.starts), y, side="right")) - 1
    index = min(max(index, 0), len(band.pieces) - 1)
    piece = band.pieces[index]
    relaxed = piece.max_residual_m in band.relaxed_residual_m
    return index, piece, relaxed


def main() -> int:
    case = load_vehicle_case(rep.CASE)
    wheel = None
    for name in ("profile", "graph", "surface"):
        candidate = getattr(case.wheels[0], name, None)
        if candidate is not None and hasattr(candidate, "y_m"):
            wheel = candidate
            break
    if wheel is None:
        raise SystemExit("wheel profile not found on the case")
    rail = next(r for r in case.rails if "right" in r.id)
    series = rail.profiles if rail.bodies == () else rail.bodies[0].series

    lo, hi = rep.WINDOWS["frog"]
    worst = None
    scanned = 0
    for s in np.linspace(lo, hi, rep.STATIONS):
        if not series.covers(float(s)):
            continue
        sample = series.sample(float(s))
        crown = int(np.argmax(sample.profile.z_m))
        crown_y = float(sample.profile.y_m[crown])
        crown_z = float(sample.profile.z_m[crown])
        for sink_mm in rep.SINKS_MM:
            for offset_mm in rep.OFFSETS_MM:
                wheel_y, wheel_z, rail_y, rail_z = _absolute_arrays(
                    wheel, sample,
                    wheel_y_m=crown_y,
                    wheel_z_m=crown_z + 0.43 - sink_mm * 1e-3,
                    wheel_roll_rad=0.0,
                    wheel_lateral_offset_m=offset_mm * 1e-3,
                    rail_y_m=0.0,
                    rail_z_m=0.0,
                )
                grid = rep._grid_solution(wheel_y, wheel_z, rail_y, rail_z)
                spline, _, _ = rep._segmented_contact(
                    wheel_y, wheel_z, rail_y, rail_z,
                    crown_y, crown_z + 0.43 - sink_mm * 1e-3)
                if grid is None or spline is None:
                    continue
                scanned += 1
                delta = abs((spline.penetration_m - grid["depth"]) * 1e6)
                if worst is None or delta > worst["delta_um"]:
                    worst = {
                        "delta_um": delta, "s_m": float(s), "sink_mm": sink_mm,
                        "offset_mm": offset_mm,
                        "spline_y_mm": spline.y_m * 1e3,
                        "spline_depth_um": spline.penetration_m * 1e6,
                        "grid_y_mm": grid["y"] * 1e3,
                        "grid_depth_um": grid["depth"] * 1e6,
                    }
    if worst is None:
        print("no comparable frog sample")
        return 1

    print(f"scanned {scanned} frog samples")
    print(f"worst |ddepth| = {worst['delta_um']:.3f} um at s = {worst['s_m']:.4f} m, "
          f"sink {worst['sink_mm']} mm, offset {worst['offset_mm']} mm")
    print(f"  spline: y = {worst['spline_y_mm']:.3f} mm, depth = {worst['spline_depth_um']:.3f} um")
    print(f"  grid  : y = {worst['grid_y_mm']:.3f} mm, depth = {worst['grid_depth_um']:.3f} um")

    # Rebuild the bands for the worst sample and inspect the owning pieces.
    sample = series.sample(worst["s_m"])
    crown = int(np.argmax(sample.profile.z_m))
    crown_y = float(sample.profile.y_m[crown])
    crown_z = float(sample.profile.z_m[crown])
    wheel_y, wheel_z, rail_y, rail_z = _absolute_arrays(
        wheel, sample,
        wheel_y_m=crown_y,
        wheel_z_m=crown_z + 0.43 - worst["sink_mm"] * 1e-3,
        wheel_roll_rad=0.0,
        wheel_lateral_offset_m=worst["offset_mm"] * 1e-3,
        rail_y_m=0.0,
        rail_z_m=0.0,
    )
    wheel_band = fit_segmented(wheel_y, wheel_z)
    rail_band = fit_segmented(rail_y, rail_z)
    for label, band, y_abs in (("wheel", wheel_band, worst["spline_y_mm"] * 1e-3),
                               ("rail", rail_band, worst["spline_y_mm"] * 1e-3)):
        index, piece, relaxed = piece_of(band, y_abs)
        print(f"  {label}: {len(band.pieces)} pieces, contact in piece #{index} "
              f"[{piece.y_lo_m * 1e3:.3f}, {piece.y_hi_m * 1e3:.3f}] mm, "
              f"fit residual {piece.max_residual_m * 1e6:.3f} um, relaxed={relaxed}")
        print(f"        band max residual {band.max_residual_m * 1e6:.3f} um, "
              f"relaxed pieces {len(band.relaxed_residual_m)}")
    # A second solve on an explicitly re-split rail band, to see whether more pieces
    # change the answer (i.e. whether depth is the limit).
    dense = swept_contact(wheel_band, rail_band,
                          wheel_origin_y_m=crown_y,
                          wheel_origin_z_m=crown_z + 0.43 - worst["sink_mm"] * 1e-3,
                          effective_modulus_pa=rep.E_STAR_PA,
                          scan_step_m=5.0e-6)
    if dense is not None:
        print(f"  rescan 5 um: y = {dense.y_m * 1e3:.3f} mm, "
              f"depth = {dense.penetration_m * 1e6:.3f} um")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
