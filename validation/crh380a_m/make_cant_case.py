"""Build a case with 1:40 rail cant (轨底坡) from an existing case.

The drawing for the 18 号 turnout states 道岔区钢轨设 1:40 的轨底坡或轨顶坡 (note
9.11). Velch previously had no representation for it: the only way was to tilt the
whole rail body about the gauge face, which raises the crown by 35/40 = 0.875 mm
and once produced a 1930 kN normal force.

Now the cant is a rotation of each rail profile about its own crown centre:

    roll_rad       = ±atan(1/40)
    roll_pivot_y_m = the rail's crown centre in track coordinates
    roll_pivot_z_m = 0

The right rail tilts so its inner edge is lower (dz/dy = +1/40); the left rail is
the mirror image (dz/dy = -1/40).
"""

from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path


def profile_specs(template: dict) -> list[dict]:
    """Every profile spec of one rail template (base stations first, then bodies)."""

    specs: list[dict] = []
    for station in template.get("stations", []):
        spec = station.get("profile")
        if isinstance(spec, dict):
            specs.append(spec)
    for body in template.get("bodies", []):
        for station in body.get("stations", []):
            spec = station.get("profile")
            if isinstance(spec, dict):
                specs.append(spec)
    return specs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ratio", type=float, default=40.0, help="1:ratio cant")
    args = parser.parse_args()

    raw = json.loads(args.case.read_text(encoding="utf-8"))
    document = copy.deepcopy(raw)
    angle = math.atan(1.0 / args.ratio)
    touched = 0
    for template in document["rail_templates"]:
        for spec in profile_specs(template):
            y_offset = float(spec.get("y_offset_m", 0.0))
            spec["roll_rad"] = angle if y_offset >= 0.0 else -angle
            spec["roll_pivot_y_m"] = y_offset
            spec["roll_pivot_z_m"] = 0.0
            touched += 1
    document["case_id"] = f"{raw['case_id']}_cant1in{args.ratio:g}"
    document["parameter_source"] = (
        raw["parameter_source"]
        + f"; rail cant 1:{args.ratio:g} as a profile rotation about the crown centre "
          "(drawing note 9.11)")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(f"wrote {args.output}  profiles={touched}  roll_rad={angle:.6f} rad")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
