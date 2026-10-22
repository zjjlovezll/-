"""S1-e full-run pair: 1.2 s turnout pass, with and without the support compliance."""

from __future__ import annotations

import json
import pathlib
import sys

BASE = pathlib.Path(__file__).resolve().parent
REFERENCE = BASE / "case_S_hc_e0.5_v0.1.json"
SPEC = {"spacing_m": 0.6, "pad_stiffness_n_m": 25e6, "rail_ei_n_m2": 6.55e6}


def build(name: str, *, compliance: dict | None, case_id: str) -> pathlib.Path:
    raw = json.loads(REFERENCE.read_text(encoding="utf-8"))
    raw["case_id"] = case_id
    raw["run"]["duration_s"] = 1.2
    raw["run"]["x_start_m"] = 13.5
    if compliance:
        raw["support_compliance"] = compliance
    else:
        raw.pop("support_compliance", None)
    target = BASE / name
    target.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def main() -> int:
    a = build("case_Y_full_base.json", compliance=None, case_id="crh380a_m_y_full_base")
    b = build("case_Y_full_support.json", compliance=SPEC, case_id="crh380a_m_y_full_support")
    for path in (a, b):
        raw = json.loads(path.read_text(encoding="utf-8"))
        print(path.name, "| duration", raw["run"]["duration_s"], "| x_start", raw["run"]["x_start_m"],
              "| output_step", raw["run"]["output_step_s"], "| bodies",
              sum(len(t.get("bodies", [])) for t in raw["rail_templates"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
