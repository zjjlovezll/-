"""Build body-attribution variants of a turnout case (plan A).

Plan A has two independent knobs, both declared in the case file so every run
states the rule it used:

``y_window_m``      lateral gate on a rail body. A head whose running surface is
                    not under the wheel tread cannot carry load, however deep
                    its crown measures. Written as ``[lo, hi]`` in absolute
                    across-track metres.
``body_hysteresis`` one body per side carries load, and the incumbent keeps it
                    until it unloads below the release threshold and a
                    challenger is deeper by the switch margin.

Usage::

    python make_attr_cases.py <base-case.json> <tag> <gate-mm> [--hysteresis]

Writes ``case_attr_<tag>_gate<gate-mm>[_hyst].json`` next to the base case.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

POINT_BODY_ID = "point"


def build(base: dict, *, case_id: str, gate_m: float | None, hysteresis: bool) -> dict:
    case = json.loads(json.dumps(base))
    touched = False
    for template in case["rail_templates"]:
        for body in template.get("bodies") or []:
            if body["id"] != POINT_BODY_ID:
                continue
            if gate_m is None:
                body.pop("y_window_m", None)
            else:
                body["y_window_m"] = [float(gate_m), 0.800]
            touched = True
    if not touched:
        raise SystemExit("base case has no 'point' rail body to gate")
    case["run"]["body_hysteresis"] = bool(hysteresis)
    case["case_id"] = case_id
    case.setdefault("purpose_detail", {})
    return case


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print(__doc__)
        return 2
    base_path = Path(argv[1])
    tag = argv[2]
    gate_mm = float(argv[3])
    hysteresis = "--hysteresis" in argv[4:]
    base = json.loads(base_path.read_text(encoding="utf-8"))
    suffix = "hyst" if hysteresis else "plain"
    case_id = f"crh380a_m_attr_{tag}_gate{gate_mm:g}_{suffix}"
    case = build(base, case_id=case_id, gate_m=gate_mm / 1000.0, hysteresis=hysteresis)
    out = base_path.parent / f"case_attr_{tag}_gate{gate_mm:g}_{suffix}.json"
    out.write_text(json.dumps(case, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{out.name}: x_start={case['run']['x_start_m']} dur={case['run']['duration_s']} "
          f"gate>={gate_mm:g} mm hysteresis={hysteresis}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
