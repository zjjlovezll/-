"""Give the reconstructed wing body the longitudinal lift a 60TY1 frog wing has.

Diagnosis from the trajectory overlay (`cmp_trajectory.py`): in the closure
section (80.0-80.5 m) Simpack's wheelset rises +0.31 mm while ours drops
-0.18 mm.  A plain 60 kg crown (what `build_wing_case.py` clones from the entry
track) has no lift at all, so as the point rail becomes reachable the contact
migrates onto its lower nose and the wheel sinks.  A real frog wing rail is a
60TY1 with an inclined running surface: its job is exactly to *lift* the wheel
onto the point rail before the point rail starts carrying load.

This script rebuilds the `wing` body of a case with a smooth longitudinal lift
``h(s)`` and keeps everything else identical:

    h(s) = h_max * sin(pi * u)**2,   u = (s - s_lo) / (s_hi - s_lo)

so the lift is zero (and C1) at both ends of the window and maximal in the
middle, where the transfer happens.  ``h_max`` is the single calibration knob.

Usage: python make_wing_rise.py <base.json> <out.json> [h_max_mm] [s_lo] [s_hi]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE.parents[1] / "src"))


def main(argv: list[str]) -> int:
    source = Path(argv[1]) if len(argv) > 1 else BASE / "case_I_wing.json"
    target = Path(argv[2]) if len(argv) > 2 else BASE / "case_J_wing_rise.json"
    h_max = (float(argv[3]) if len(argv) > 3 else 0.5) / 1e3
    s_lo = float(argv[4]) if len(argv) > 4 else 79.60
    s_hi = float(argv[5]) if len(argv) > 5 else 81.20
    # A 60TY1 wing rail does not carry a flat crown: its running surface is
    # inclined across the head (order 1:40), highest on the side that hands the
    # wheel over to the point rail.  The slope is applied about `y_ref` so the
    # body keeps its lateral position and only its top surface tilts.
    lateral_slope = float(argv[6]) if len(argv) > 6 else 0.0
    y_ref = float(argv[7]) if len(argv) > 7 else 0.780

    case = json.loads(source.read_text(encoding="utf-8"))
    right = max(
        case["rail_templates"],
        key=lambda t: max(
            [float(b["stations"][0]["profile"].get("y_offset_m", 0.0)) for b in t.get("bodies") or ()] or [0.0]
        ),
    )
    wing = next(b for b in right["bodies"] if b["id"] == "wing")
    stations = sorted(wing["stations"], key=lambda st: st["s_m"])

    # Rewrite the wing stations: shift every crown point of the cloned crown up
    # by h(s).  Each lift gets its own directory: a shared directory would let the
    # last write silently replace every earlier rise's geometry, making the sweep
    # reproducible only in the order it happened to run.
    tag = f"{h_max * 1e3:.2f}".replace(".", "p")
    if lateral_slope:
        tag = f"{tag}_s{abs(lateral_slope) * 1e3:.0f}"
    out_dir = BASE / f"bodies_wing_rise{tag}"
    out_dir.mkdir(exist_ok=True)
    from velch.profiles import load_profile  # noqa: PLC0415

    new_stations = []
    for st in stations:
        spec = st["profile"]
        scale = 1e-3 if spec.get("units", "m") == "mm" else 1.0
        graph = load_profile(
            Path(spec["file"]), file_format=spec.get("format", "csv"), surface="rail_top",
            y_scale_m=scale, z_scale_m=scale,
            y_sign=int(spec.get("y_sign", 1)), z_sign=int(spec.get("z_sign", 1)),
            y_offset_m=float(spec.get("y_offset_m", 0.0)),
            z_offset_m=float(spec.get("z_offset_m", 0.0)),
        )
        s_m = float(st["s_m"])
        u = min(max((s_m - s_lo) / (s_hi - s_lo), 0.0), 1.0)
        h = h_max * np.sin(np.pi * u) ** 2
        name = out_dir / f"wing_r{s_m * 1000.0:07.0f}.csv"
        tilt = lateral_slope * (y_ref - graph.y_m) if lateral_slope else np.zeros_like(graph.y_m)
        with name.open("w", encoding="utf-8") as handle:
            # Two bare columns: the loader rejects a header row.
            for y, z, t in zip(graph.y_m, graph.z_m, tilt):
                handle.write(f"{y * 1e3:.6f},{z * 1e3 + h * 1e3 + t * 1e3:.6f}\n")
        new_stations.append({
            "id": f"W{s_m * 1000.0:07.0f}",
            "s_m": s_m,
            "profile": {"file": str(name.relative_to(BASE)).replace("\\", "/"),
                        "format": "csv", "units": "mm"},
        })

    wing["stations"] = new_stations
    case["case_id"] = f"{case['case_id']}_rise{h_max * 1e3:.2f}"
    case["purpose_detail"] = (
        f"{case.get('purpose_detail', '')} | wing body carries a 60TY1-style lift "
        f"h_max={h_max * 1e3:.3f} mm over {s_lo:.2f}-{s_hi:.2f} m (calibration knob)"
    ).strip(" |")
    target.write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {target.name}: wing lift h_max {h_max * 1e3:.3f} mm over "
          f"{s_lo:.2f}-{s_hi:.2f} m, {len(new_stations)} stations -> {out_dir.name}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
