"""S1-e: frog-window pair (with / without the 600 mm rail-support compliance)."""

from __future__ import annotations

import json
import pathlib
import sys

BASE = pathlib.Path(__file__).resolve().parent
REFERENCE = BASE / "case_frog_N_strip05.json"
SPEC = {"spacing_m": 0.6, "pad_stiffness_n_m": 25e6, "rail_ei_n_m2": 6.55e6}


def build(out_name: str, *, compliance: dict | None, case_id: str) -> pathlib.Path:
    raw = json.loads(REFERENCE.read_text(encoding="utf-8"))
    raw["case_id"] = case_id
    if compliance:
        raw["support_compliance"] = compliance
    else:
        raw.pop("support_compliance", None)
    target = BASE / out_name
    target.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def main() -> int:
    a = build("case_X_support_base.json", compliance=None, case_id="crh380a_m_x_support_base")
    b = build("case_X_support.json", compliance=SPEC, case_id="crh380a_m_x_support")
    for path in (a, b):
        print(path.name, path.stat().st_size, "bytes")
    print("reference:", REFERENCE.name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
