"""Fill the switch-rail seat notch in the curved stock rail without changing the node count.

The feature
-----------
At the switch panel the curved stock rail's head is undercut so the switch rail can seat in it; the
undercut is a 16--23 mm deep notch in the profile.  A merged profile never picks it, but once the stock
rail is its own body the contact search treats the notch floor as the "deepest point" and drives the
wheelset into it (measured: 16.06 mm penetration, 64.0 kN).

First attempt clipped the contour to the running band, which changed the point count per station; the
profile series computes ``dz_ds`` from neighbouring stations and needs a common node grid, so it
produced a non-finite gradient and the solver refused with ``ProfileError: longitudinal profile
derivative is undefined``.  This version keeps every station on its original grid and only *raises* z:
anything more than ``CAP_M`` below the crown is lifted to the crown minus ``CAP_M``.  The node count is
untouched, so the longitudinal derivative stays well defined, and the notch can no longer swallow the
wheel.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "src"))

from velch.vehicle import load_vehicle_case  # noqa: E402

CAP_M = 0.0005


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", default="case_diverging_multi.json")
    parser.add_argument("--output", default="case_diverging_clipped.json")
    parser.add_argument("--dir", default="div_panel")
    parser.add_argument("--cap-mm", type=float, default=CAP_M * 1e3)
    args = parser.parse_args()
    cap = args.cap_mm / 1e3

    raw = json.loads((HERE / args.case).read_text(encoding="utf-8"))
    case = load_vehicle_case(HERE / args.case)
    rail = next(r for r in case.rails if r.id.endswith("right") and r.axle_index == 0)
    stock = next(body for body in (getattr(rail, "contact_bodies", None) or [])
                 if body.id == "stock")
    target = next(t for t in raw["rail_templates"] if t.get("bodies"))
    stock_raw = next(body for body in target["bodies"] if body["id"] == "stock")

    out_dir = HERE / args.dir
    out_dir.mkdir(exist_ok=True)
    lifted_total = 0.0
    rewritten = 0
    for entry in stock_raw["stations"]:
        station = float(entry["s_m"])
        sample = stock.series.sample(station, 1)
        profile = getattr(sample, "profile", sample)
        y = np.asarray(profile.y_m, dtype=float)
        z = np.asarray(profile.z_m, dtype=float)
        crown = float(z.max())
        floor = crown - cap
        lifted = z < floor
        if not lifted.any():
            continue
        lifted_total = max(lifted_total, float(floor - z[lifted].min()))
        z_new = np.maximum(z, floor)
        name = f"stock_r{station:010.4f}.csv"
        with (out_dir / name).open("w", encoding="ascii") as handle:
            for index in range(y.size):
                handle.write(f"{y[index]:.9f},{z_new[index]:.9f}\n")
        entry["profile"] = {"file": f"{args.dir}/{name}", "format": "csv", "units": "m"}
        rewritten += 1

    output = HERE / args.output
    output.write_text(json.dumps(raw, indent=1), encoding="utf-8")
    print(f"stock stations {len(stock_raw['stations'])}, rewritten {rewritten}, "
          f"deepest lift {lifted_total * 1e3:.2f} mm (cap {args.cap_mm:.1f} mm)")
    print(f"wrote {output.name} (+{rewritten} csv, node counts unchanged)")

    loaded = load_vehicle_case(output)
    body = next(b for r in loaded.rails if r.id.endswith("right")
                for b in (getattr(r, "contact_bodies", None) or []) if b.id == "stock")
    probe = min((float(e["s_m"]) for e in stock_raw["stations"]), key=lambda s: abs(s - 60.0))
    sample = body.series.sample(probe, 1)
    profile = getattr(sample, "profile", sample)
    finite = bool(np.isfinite(np.asarray(sample.dz_ds, dtype=float)).all())
    print(f"round-trip at {probe:.3f} m: {profile.y_m.size} points, "
          f"z {profile.z_m.min()*1e3:.2f}..{profile.z_m.max()*1e3:.2f} mm, "
          f"dz_ds finite = {finite}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
