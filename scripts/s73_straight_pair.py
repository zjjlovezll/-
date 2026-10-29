"""Build a straight through-route pair: both rails held at constant lateral offsets.

The case built in round 12 (`scratch/s64/case_gap.json`) rewrote only the RIGHT rail's sections to
the plain stock profile and left the left template on the diverging station table.  Measured
consequence (crown positions, `s72`):

    s_m     L crown y (m)   R crown y (m)   gauge (mm)
    40.0      -0.7602         +0.7469        1507.1
    80.0      -0.3670         +0.7469        1113.9
    95.0      +0.1362         +0.7469         610.7
    110.0     +0.8437         +0.7469         -96.8

So beyond about 60 m the "left" rail has followed the curve across to the other side of the right
rail: seating at 95 m cannot balance and reports
``unbalanced branch - 4 of 8 wheels carry load ... heaviest 119389.4 N``.  That is a *data* defect
of the half-repaired case, not a solver failure, and it is why the rigid straight route only ever
ran near 40 m.

This script finishes the repair the other way round: keep the diverging geometry out of the pair by
pinning **both** rails' crowns to constant lateral offsets (the round-305B gauge 1.50649 split about
the through centre), so the pair is a straight track for every mileage and the only mileage-varying
quantity left is the height of the switch/blade body.

The lateral offset is set from the *crown*, not from the profile midpoint, because the two section
families carry their crowns asymmetrically (left -6.8 mm, right +6.7 mm from their own midpoint);
that asymmetry is exactly what made the round-305B gauge normalisation land 26/62 mm off when it used
midpoints.

Recompute::

    cd F:/ai道岔状态反演辨识/Velch
    PYTHONPATH=src python -X utf8 scripts/s73_straight_pair.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from velch.profiles import load_profile

HERE = Path(__file__).resolve().parents[1]
DEFAULT_CASE = Path("../scratch/s64/case_gap.json")
HALF_GAUGE_M = 1.50649 / 2.0
CROWN_TARGET_RIGHT_M = +HALF_GAUGE_M
CROWN_TARGET_LEFT_M = -HALF_GAUGE_M


def _transform_key(spec: dict) -> tuple:
    """Cache key must carry the transform, not only the file.

    Measured: keying on the file alone returned the *mirrored* crown offset for the unmirrored
    rail too, which placed the right crown at +0.76713 m instead of +0.75325 m (13.88 mm out
    = 2 x 6.94 mm) and made the seat report four of eight wheels on a symmetric pair.
    """
    return (
        spec["file"],
        int(spec.get("y_sign", 1)),
        int(spec.get("z_sign", 1)),
        str(spec.get("format", "prr")),
    )


def _crown_offset(spec: dict, cache: dict[tuple, float]) -> float:
    """Distance from the profile's own `y_offset_m` to its highest point."""
    file = _transform_key(spec)
    if file not in cache:
        profile = load_profile(
            Path(spec["file"]),
            file_format=str(spec.get("format", "prr")),
            surface="rail_top",
            y_sign=int(spec.get("y_sign", 1)),
            z_sign=int(spec.get("z_sign", 1)),
        )
        cache[file] = float(profile.y_m[int(np.argmax(profile.z_m))])
    return cache[file]


def _crown_z(spec: dict, cache: dict[tuple, float]) -> float:
    """Height of the profile's highest point, including its own z offset."""
    key = ("z",) + _transform_key(spec)
    if key not in cache:
        profile = load_profile(
            Path(spec["file"]),
            file_format=str(spec.get("format", "prr")),
            surface="rail_top",
            y_sign=int(spec.get("y_sign", 1)),
            z_sign=int(spec.get("z_sign", 1)),
        )
        cache[key] = float(profile.z_m.max())
    return cache[key] + float(spec.get("z_offset_m", 0.0))


def _pin(stations: list[dict], target_m: float, cache: dict[str, float]) -> float:
    worst = 0.0
    for station in stations:
        spec = station["profile"]
        offset = _crown_offset(spec, cache)
        spec["y_offset_m"] = float(target_m - offset)
    for station in (stations[0], stations[len(stations) // 2], stations[-1]):
        spec = station["profile"]
        crown = _crown_offset(spec, cache) + float(spec["y_offset_m"])
        worst = max(worst, abs(crown - target_m))
    return worst


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default=str(DEFAULT_CASE))
    parser.add_argument("--out", default="../scratch/s73")
    parser.add_argument(
        "--keep-two-families",
        action="store_true",
        help="keep the left rail on its own mileage table instead of mirroring the right section",
    )
    parser.add_argument(
        "--keep-cross-level",
        action="store_true",
        help="keep the 72 um crown-height difference between the two section families",
    )
    options = parser.parse_args()

    out = Path(options.out)
    out.mkdir(parents=True, exist_ok=True)
    raw = json.loads(Path(options.case).read_text(encoding="utf-8"))
    cache: dict[tuple, float] = {}

    if not options.keep_two_families:
        # A plain track is ONE section family mirrored, not two different rails.  Leaving the left
        # template on `Profile_Mileage_JBG` and the right on `jbg-20200418-R` makes the model invent
        # an asymmetry: at 40 m the seat returned 77.0 kN left / 42.6 kN right (1.29x / 0.71x) on a
        # geometrically symmetric pair, because the two families have different crown curvature and
        # therefore different contact stiffness at the same penetration.
        right_template = next(item for item in raw["rail_templates"] if item["id"] == "right")
        right_body = (right_template.get("bodies") or [{"stations": right_template["stations"]}])[0]
        source = dict(right_body["stations"][0]["profile"])
        left_template = next(item for item in raw["rail_templates"] if item["id"] == "left")
        left_bodies = left_template.get("bodies") or [{"id": left_template["id"], "stations": left_template["stations"]}]
        for body in left_bodies:
            for station in body["stations"]:
                spec = dict(source)
                spec["y_sign"] = -1 * int(source.get("y_sign", 1))
                station["profile"] = spec
        print(f"left rail rewritten to mirror {Path(str(source['file'])).name} "
              f"({sum(len(body['stations']) for body in left_bodies)} stations)")
    report = {}
    for template in raw["rail_templates"]:
        target = CROWN_TARGET_LEFT_M if template["id"] == "left" else CROWN_TARGET_RIGHT_M
        bodies = template.get("bodies") or [{"id": template["id"], "stations": template["stations"]}]
        worst = 0.0
        for body in bodies:
            worst = max(worst, _pin(body["stations"], target, cache))
        report[template["id"]] = {"target_crown_m": target, "worst_crown_error_m": worst}
        print(f"{template['id']:>6}: crown pinned to {target:+.5f} m, "
              f"{sum(len(body['stations']) for body in bodies)} stations, "
              f"worst error {worst * 1e6:.3f} um")

    if not options.keep_cross_level:
        # The two section families disagree about their own crown height by 72.4 um -- the same
        # order as the 65.47 um static penetration, so the seat cannot balance the pair.  This is a
        # property of mixing `Profile_Mileage_JBG` (left) with `jbg-20200418-R` (right), not a
        # design cross-level: a plain track has none.  Recorded, and removed in the built case.
        left_template = next(item for item in raw["rail_templates"] if item["id"] == "left")
        left_body = (left_template.get("bodies") or [{"stations": left_template["stations"]}])[0]
        reference = _crown_z(left_body["stations"][0]["profile"], cache)
        right_template = next(item for item in raw["rail_templates"] if item["id"] == "right")
        right_bodies = right_template.get("bodies") or [{"stations": right_template["stations"]}]
        shifts = []
        for body in right_bodies:
            # Only the through-route surface is levelled.  A blade or frog body carries its
            # lowering *as* a height difference (round 208: +0.268 mm offset gave +0.268 mm of load
            # equivalent), so levelling it would erase the very quantity P1 must recover.  Measured
            # here: without this filter the shift ranged -72.40..+13928.00 um, i.e. it would have
            # lifted the blade body 13.9 mm.
            if body is not right_bodies[0]:
                print(f"  leaving body {body['id']} alone ({len(body['stations'])} stations)")
                continue
            for station in body["stations"]:
                spec = station["profile"]
                shift = reference - _crown_z(spec, cache)
                spec["z_offset_m"] = float(spec.get("z_offset_m", 0.0)) + shift
                shifts.append(shift)
        print(f"cross-level removed: right rail shifted by {np.mean(shifts) * 1e6:+.2f} um "
              f"({np.min(shifts) * 1e6:+.2f}..{np.max(shifts) * 1e6:+.2f}) so both crowns sit at "
              f"{reference:+.6f} m")
        report["cross_level_removed_m"] = float(np.mean(shifts))

    raw["case_id"] = f"{raw['case_id']}_straight_pair"
    raw["purpose_detail"] = (
        str(raw.get("purpose_detail", ""))
        + " | straight pair: both rail crowns pinned to a constant 1.50649 m gauge (s73)"
    )
    target_path = out / "case_straight_pair.json"
    target_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    (out / "straight_pair_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    print("wrote", target_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
