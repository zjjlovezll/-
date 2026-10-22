"""Clone a Velch case and enable the discretised (patch-averaged) Hertz contact.

The vendor model runs ``rw.cont.meth = 2`` (discrete elastic) with
``cont_disc_delta = 5e-4``: the normal force is resolved over a patch of finite
lateral extent instead of a single point.  This script exposes that behaviour in
Velch through ``contact.patch_half_width_m`` / ``contact.patch_slices`` so the
rail-transfer step can be evaluated with and without it.

Hertz half-width for the CRH380A_M case: a = (3 N R / (4 E*))**(1/3) with
N ~ 60 kN, R = 0.02 m, E* = 1.1393e11 Pa  ->  a = 1.99 mm, 2a = 3.98 mm.
Nine slices over +/-2 mm give a 0.5 mm spacing, matching ``cont_disc_delta``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source")
    parser.add_argument("target")
    parser.add_argument("--half-width-mm", type=float, default=2.0)
    parser.add_argument("--slices", type=int, default=9)
    args = parser.parse_args()

    source = Path(args.source)
    payload = json.loads(source.read_text(encoding="utf-8"))
    contact = payload.setdefault("contact", {})
    contact["patch_half_width_m"] = args.half_width_mm * 1e-3
    contact["patch_slices"] = args.slices
    payload["case_id"] = f"{payload.get('case_id', source.stem)}_patch{args.half_width_mm:g}mm"

    target = Path(args.target)
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"wrote {target}  patch_half_width={contact['patch_half_width_m']:.4g} m  "
        f"slices={contact['patch_slices']}  case_id={payload['case_id']}"
    )


if __name__ == "__main__":
    main()
