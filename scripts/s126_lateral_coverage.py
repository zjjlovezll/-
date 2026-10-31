"""M7 step 4: how many passes does the light band need?  A geometric answer from seated states.

Round 259 measured how far sideways one pass can see a surface feature: 4 mm at the 1 % response level,
3.6 mm at 10 %, 1.7 mm at half.  Against a 37.15 mm head that is nine passes at 4 mm spacing -- but that
arithmetic assumed the *contact band* could be moved across the head at will, and nothing had measured
whether the passes actually land on different lateral positions.

This script answers that with seated states only (no time history, seconds per pass).  The lever that
moves the contact across the head is a **gauge change**: the right rail's stations are shifted laterally
by `delta`, so the two rails sit `delta` mm further apart.  Real service gauge variation is a few
millimetres; the sweep goes to +-8 mm to see where the mechanism stops working, and says so.

For each delta it reports:

* whether the case seats at all (a failed seat is a pass that does not exist);
* each contact's lateral position **relative to its own rail's crown** and its half-width, i.e. which
  part of the head the pass actually sees;
* the union of the bands over the passes, against the head width, i.e. the coverage a campaign of these
  passes would achieve.

Pre-registered before running: a pass counts only if the seat residual is <= 1e-5 N and all eight
contacts are active.  Coverage is `|union of bands intersect head| / |head|`, head measured from the
stock section as the 5 mm-deep span (61.46 mm per round 249), and the band taken as the contact's
`[y - half_width, y + half_width]`.

Writes ``reports/load_split_inversion_2026-10-31/lateral_coverage.json``.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from velch.vehicle import load_vehicle_case  # noqa: E402
from velch.vehicle_solver import VehicleDynamics, _seat  # noqa: E402

CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
OUT = ROOT.parent / "scratch" / "s126"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "lateral_coverage.json"

DELTAS_MM = (-8.0, -6.0, -4.0, -2.0, 0.0, 2.0, 4.0, 6.0, 8.0)
SPEED_KMH = 80.0
SEAT_RESIDUAL_LIMIT_N = 1e-5
HEAD_DEPTH_M = 0.005
STATION_M = 58.5


def _variant(delta_mm: float) -> pathlib.Path:
    """Shift the right rail laterally by delta (a gauge change), leaving everything else alone."""
    raw = json.loads(CASE.read_text(encoding="utf-8"))
    raw["case_id"] = f"{raw['case_id']}_gauge{delta_mm:+.0f}mm"
    raw["purpose_detail"] = (f"coverage variant: right rail shifted laterally by {delta_mm:+.1f} mm, "
                             f"a gauge change, to move the contact across the head")
    for index, template in enumerate(raw["rail_templates"]):
        if index != 1:
            continue  # only the right rail moves
        for station in template["stations"]:
            station["profile"]["y_offset_m"] = float(
                station["profile"].get("y_offset_m", 0.0)) + delta_mm * 1e-3
        for body in template.get("bodies") or []:
            for station in body["stations"]:
                station["profile"]["y_offset_m"] = float(
                    station["profile"].get("y_offset_m", 0.0)) + delta_mm * 1e-3
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"one_set_gauge{delta_mm:+.0f}mm.json"
    path.write_text(json.dumps(raw, indent=1, ensure_ascii=False) + chr(10), encoding="utf-8")
    return path


def _crown_table() -> dict[str, tuple[float, float]]:
    """rail id -> (crown y at STATION_M, head width from the 5 mm deep span)."""
    case = load_vehicle_case(CASE)
    out = {}
    for rail in case.rails:
        body = rail.contact_bodies[0]
        sample = body.series.sample(STATION_M, 1.0)
        y = np.asarray(sample.profile.y_m, dtype=float)
        z = np.asarray(sample.profile.z_m, dtype=float)
        crown = float(y[int(np.argmax(z))])
        deep = z >= (float(np.max(z)) - HEAD_DEPTH_M)
        band = y[deep]
        out[rail.id] = (crown, float(np.max(band) - np.min(band)))
    return out


def seat_one(path: pathlib.Path, crowns: dict[str, tuple[float, float]]) -> dict:
    case = load_vehicle_case(path)
    dynamics = VehicleDynamics(case)
    state = np.asarray(case.initial_q, dtype=float)
    velocity = np.asarray(case.initial_v, dtype=float)
    spin = dynamics.topology.require("wheelset1", "spin")
    velocity[spin] = SPEED_KMH / 3.6 / 0.43
    with np.errstate(all="ignore"):
        seated, residual = _seat(case, dynamics, state, velocity)
    _, contacts = dynamics.evaluate(0.0, seated, velocity)

    rows = []
    all_active = True
    for rail_id, response in contacts.items():
        active = bool(getattr(response, "active", False)) and response.geometry is not None
        all_active = all_active and active
        if not active:
            rows.append({"rail": rail_id, "active": False})
            continue
        crown, head = crowns.get(rail_id, (float("nan"), float("nan")))
        y_c = float(response.geometry.y_m)
        half = float(response.geometry.half_width_m)
        rows.append({"rail": rail_id, "active": True, "contact_y_m": y_c,
                     "crown_y_m": crown, "offset_from_crown_mm": 1e3 * (y_c - crown),
                     "half_width_mm": 1e3 * half, "normal_force_n": float(response.normal_force_n),
                     "head_width_mm": 1e3 * head})
    ok = all_active and float(residual) <= SEAT_RESIDUAL_LIMIT_N
    return {"route": path.stem, "seat_residual_n": float(residual), "all_eight_active": all_active,
            "pass_ok": bool(ok), "contacts": rows}


def coverage(passes: list[dict], head_width_m: float, step_mm: float = 0.1) -> dict:
    """Union of the right-side contact bands, in crown-relative mm, against the head width."""
    grid = np.arange(-head_width_m * 1e3 / 2.0, head_width_m * 1e3 / 2.0, step_mm)
    covered = np.zeros_like(grid, dtype=bool)
    bands = []
    for entry in passes:
        if not entry["pass_ok"]:
            continue
        for row in entry["contacts"]:
            if not row.get("active") or not row["rail"].endswith("_right"):
                continue
            centre = row["offset_from_crown_mm"]
            half = row["half_width_mm"]
            bands.append((centre - half, centre + half))
            covered |= (grid >= centre - half) & (grid <= centre + half)
    return {"bands_mm": [[float(a), float(b)] for a, b in bands],
            "coverage": float(covered.mean()) if len(grid) else 0.0,
            "covered_mm": float((grid[covered].max() - grid[covered].min()) if covered.any() else 0.0),
            "head_width_mm": float(head_width_m * 1e3)}


def main() -> int:
    crowns = _crown_table()
    head_width = float(np.median([head for _, head in crowns.values()]))
    print(f"head width from the 5 mm span: {1e3 * head_width:.2f} mm "
          f"(per-rail {min(1e3 * h for _, h in crowns.values()):.1f}.."
          f"{max(1e3 * h for _, h in crowns.values()):.1f})")

    passes = []
    for delta in DELTAS_MM:
        entry = seat_one(_variant(delta), crowns)
        entry["delta_mm"] = delta
        passes.append(entry)
        right = [row for row in entry["contacts"] if row.get("active") and row["rail"].endswith("_right")]
        offsets = ", ".join(f"{row['offset_from_crown_mm']:+.1f}" for row in right) or "-"
        print(f"delta {delta:+5.1f} mm  seat {entry['seat_residual_n']:.2e} N  "
              f"active {sum(1 for row in entry['contacts'] if row.get('active'))}/8  "
              f"pass {'OK ' if entry['pass_ok'] else 'FAIL'}  right offsets {offsets}")

    result = coverage(passes, head_width)
    ok_passes = sum(1 for entry in passes if entry["pass_ok"])
    verdict = (f"{ok_passes}/{len(passes)} gauge settings seat; their bands cover "
               f"{100.0 * result['coverage']:.1f} % of the {1e3 * head_width:.1f} mm head "
               f"({result['covered_mm']:.1f} mm of it)")
    print()
    print(verdict)
    payload = {"head_width_mm": 1e3 * head_width, "station_m": STATION_M,
               "deltas_mm": list(DELTAS_MM), "passes": passes,
               "passes_ok": ok_passes, "coverage": result, "verdict": verdict}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + chr(10), encoding="utf-8")
    print(f"report -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
