"""Clone a case and override the normal-force stiffness policy.

The legacy cases carry ``effective_radius_m = 0.02`` (a hand-set value). The
curvature-derived policy computes the equivalent radius from the two profiles'
local transverse curvatures at every contact point instead, so nothing has to be
tuned. Because peak force and contact loss are coupled through the contact
stiffness, the wing lift has to be re-scanned whenever this changes.

Usage:
    python -X utf8 make_stiff_variant.py <base.json> <out.json> \
        [--policy local_circular|fixed_effective_radius] [--radius-m 0.5407] \
        [--ellipticity 1.0] [--title TEXT]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base")
    parser.add_argument("out")
    parser.add_argument("--policy", choices=("local_circular", "fixed_effective_radius"),
                        default="local_circular")
    parser.add_argument("--radius-m", type=float, default=None)
    parser.add_argument("--ellipticity", type=float, default=None)
    parser.add_argument("--title", default=None)
    args = parser.parse_args()

    raw = json.loads(Path(args.base).read_text(encoding="utf-8"))
    contact = raw.setdefault("contact", {})
    contact["stiffness_policy"] = args.policy
    if args.radius_m is not None:
        contact["effective_radius_m"] = args.radius_m
    if args.ellipticity is not None:
        contact["ellipticity_correction"] = args.ellipticity
    if args.title:
        raw["case_id"] = args.title

    out = Path(args.out)
    out.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({
        "out": str(out),
        "stiffness_policy": contact["stiffness_policy"],
        "effective_radius_m": contact.get("effective_radius_m"),
        "ellipticity_correction": contact.get("ellipticity_correction", 1.0),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
