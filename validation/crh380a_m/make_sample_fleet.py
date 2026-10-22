"""S3 baseline: build a fleet of short-window cases that differ only in theta.

This is the sample generator the inverse problem needs. Each case perturbs the two
fastener parameters the identifiability gate proved observable in the frog window
(k_z, c_z) and keeps everything else bit-identical, so the fleet is a controlled
theta sweep rather than a random blob.
"""

from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "case_inverse_window.json"
FLEET = BASE
THETA = (
    (0.85, 0.85),
    (1.00, 1.00),
    (1.15, 1.15),
    (0.90, 1.10),
)


def main() -> int:
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    support = raw["rail_templates"][0]["support"]
    base_kz = float(support["k_z_n_m"])
    base_cz = float(support["c_z_n_s_m"])
    FLEET.mkdir(exist_ok=True)
    for index, (k_scale, c_scale) in enumerate(THETA):
        case = json.loads(json.dumps(raw))
        case["case_id"] = f"fleet_{index:02d}_k{k_scale:.2f}c{c_scale:.2f}"
        case["parameter_source"] = (
            f"{raw.get('parameter_source', '')} | fleet theta: "
            f"k_z x{k_scale:.2f}, c_z x{c_scale:.2f}"
        )
        case["purpose_detail"] = (
            f"theta sweep sample {index}: fastener k_z = {base_kz * k_scale:.6g} N/m, "
            f"c_z = {base_cz * c_scale:.6g} N*s/m"
        )
        for template in case["rail_templates"]:
            template["support"]["k_z_n_m"] = base_kz * k_scale
            template["support"]["c_z_n_s_m"] = base_cz * c_scale
        path = FLEET / f"{case['case_id']}.json"
        path.write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{path.name}  k_z={base_kz * k_scale:.4g}  c_z={base_cz * c_scale:.4g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
