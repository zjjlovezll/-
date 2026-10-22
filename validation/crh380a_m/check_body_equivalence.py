"""Does the split into rail bodies change the effective running surface?

The wing case replaces the merged ``main`` body with a synthetic level crown and
keeps ``point`` for the nose. If the multi-body envelope is not identical to the
raw PRR envelope, the split itself altered the geometry - and any contact loss
must be blamed on us, not on the profile file.

Usage:
    python -X utf8 check_body_equivalence.py case_I_wing.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from velch.profiles import load_profile  # noqa: E402
from velch.vehicle import load_vehicle_case  # noqa: E402

STATIONS = (79.0, 79.4, 79.8, 79.92, 80.0, 80.1, 80.2, 80.28, 80.4, 80.6, 80.9, 81.2)
Y_BAND = (0.700, 0.860)


def raw_envelope(catalog_path: Path, s_m: float) -> tuple[np.ndarray, np.ndarray]:
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    entries = [e for e in catalog["profile_references"] if e["side"] == "right"]
    best = min(entries, key=lambda e: abs(float(e["station_m"]) - s_m))
    if abs(float(best["station_m"]) - s_m) > 1e-9:
        raise SystemExit(f"no catalogue station at s={s_m} (nearest {best['station_m']})")
    profile = load_profile(Path(best["path"]), file_format="prr", surface="rail_top",
                           z_sign=-1, y_offset_m=0.753)
    return profile.y_m, profile.z_m


def main(case_path: str) -> None:
    case = load_vehicle_case(case_path)
    rail = next(r for r in case.rails if r.id == "axle1_right")
    print(f"case {case.case_id}: right rail has {len(rail.contact_bodies)} bodies")
    for body in rail.contact_bodies:
        print(f"  body {body.id:<6} s=[{body.s_lo_m:.3f}, {body.s_hi_m:.3f}]"
              f" y_window={body.y_window_m}")
    catalog = Path(case_path).resolve().parents[2] / "diagnostics" / "crh380a_m_track_catalog.json"
    reference = json.loads(catalog.read_text(encoding="utf-8"))
    right = sorted({round(float(e["station_m"]), 6) for e in reference["profile_references"]
                    if e["side"] == "right"})
    stations = [s for s in right if 79.0 <= s <= 81.5]
    worst = 0.0
    print(f"\n{'s(m)':>8}{'body max(mm)':>14}{'raw max(mm)':>13}{'delta(mm)':>11}"
          f"{'  worst y (mm)':>15}")
    for s_m in stations:
        grid = np.arange(Y_BAND[0], Y_BAND[1], 5e-5)
        stacked = []
        for body in rail.contact_bodies:
            if not body.active_at(s_m) or not body.series.covers(s_m):
                continue
            sample = body.series.sample(s_m, 1)
            y = sample.profile.y_m + 0.753
            z = sample.profile.z_m
            stacked.append(np.interp(grid, y, z, left=np.nan, right=np.nan))
        if not stacked:
            continue
        with np.errstate(all="ignore"):
            body_surface = np.nanmax(np.vstack(stacked), axis=0)
        raw_y, raw_z = raw_envelope(catalog, s_m)
        raw_surface = np.interp(grid, raw_y, raw_z, left=np.nan, right=np.nan)
        both = np.isfinite(body_surface) & np.isfinite(raw_surface)
        if not bool(both.any()):
            continue
        delta = body_surface[both] - raw_surface[both]
        index = int(np.argmax(np.abs(delta)))
        magnitude = float(np.max(np.abs(delta)))
        worst = max(worst, magnitude)
        if magnitude > 2.0e-4 or s_m in (79.131, 79.92, 80.0044, 80.278, 80.911):
            print(f"{s_m:>8.4f}{1e3 * float(np.nanmax(body_surface)):>14.4f}"
                  f"{1e3 * float(np.nanmax(raw_surface)):>13.4f}"
                  f"{1e3 * float(delta[index]):>11.4f}{1e3 * float(grid[both][index]):>15.3f}")
    print(f"\nstations compared: {len(stations)}")
    print(f"worst |body - raw| over the band: {1e3 * worst:.4f} mm")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "case_I_wing.json")
