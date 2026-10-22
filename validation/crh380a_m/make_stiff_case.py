"""Rebuild the frog-window case with a curvature-derived Hertz stiffness.

The case files carry `contact.effective_radius_m = 0.02`, which is one of the
hand-set numbers flagged earlier.  Simpack's own force/penetration pairs imply

    C = N / delta^1.5 = 1.117e11  (p10 9.97e10, p90 1.29e11)

and with `F = (4/3) E* sqrt(R*) delta^1.5`, `E* = 1.1393e11` this gives

    R* = (C / ((4/3) E*))^2 = 0.5407 m

which is the same order as the STRIPES equivalent radius
`rho = 4 / (1/R_yy_w + 1/R_xx_w + 1/R_xx_r)` evaluated on LMA + 60 kg
(rolling radius 0.43 m, rail crown ~0.3 m -> rho ~ 0.55-0.71 m).  The MATLAB
`Par_Hertz` / `Re_Radius` pair computes exactly this quantity per contact point.

This script only changes `effective_radius_m`; nothing else in the case moves.
"""

from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
SOURCE = HERE / "case_frog_I_wing_0p05s.json"

RADIUS = {
    "0.02": 0.02,
    "curvature": 0.540674,
}


def main() -> bool:
    which = sys.argv[1] if len(sys.argv) > 1 else "curvature"
    if which not in RADIUS:
        raise SystemExit(f"unknown radius preset {which!r}; choose from {sorted(RADIUS)}")
    case = json.loads(SOURCE.read_text(encoding="utf-8"))
    contact = case["contact"]
    print("before:", contact.get("effective_radius_m"))
    contact["effective_radius_m"] = RADIUS[which]
    stem = SOURCE.stem.replace("_I_wing_", f"_J_{which}_")
    target = HERE / f"{stem}.json"
    case["case_id"] = f"{case['case_id']}_R{which}"
    target.write_text(json.dumps(case, ensure_ascii=False, indent=2), encoding="utf-8")
    print("after :", contact["effective_radius_m"])
    print("written", target.name)
    return True


if __name__ == "__main__":
    main()
