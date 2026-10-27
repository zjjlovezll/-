"""Three archives that prove a constant speed profile is only a restatement of the field.

The acceptance criterion for the speed schedule is that adding

    "run": {"speed_profile": {"constant": <same speed>, "duration_s": ..., "unit": "m_s"}}

to a case that already declares ``travel_speed_m_s`` must not change one byte of ``history.csv``.
Two straight cases were already covered by tests; this script adds the third — the turnout — and
prints the three hashes side by side so the evidence can be read without running pytest.

    python -X utf8 scripts/s12_profile_equivalence.py
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys
import time

import numpy as np

from velch import data_root
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import save_vehicle_result, simulate_vehicle

WORK = pathlib.Path(r"F:\velch_tmp\s12")

CASES = (
    ("straight_rigid", "case_A_final_law.json", 0.015, 60.0),
    ("turnout_short", "case_frog_N_strip05.json", 0.015, 78.8),
    ("turnout_full", "case_frog_N_strip05.json", 0.05, 78.8),
)


def absolutise(node, base: pathlib.Path):
    """Make every relative profile reference absolute, so the copy can live anywhere.

    A profile name without a prefix resolves against the *case file's own folder*, so a derived case
    written to a temporary directory loses its rails (``AssetRefError: cannot resolve profile
    'bodies/main_r0791310.csv'``) even though nothing about the simulation changed.
    """

    if isinstance(node, dict):
        return {key: absolutise(value, base) for key, value in node.items()}
    if isinstance(node, list):
        return [absolutise(value, base) for value in node]
    if isinstance(node, str) and node.lower().endswith((".csv", ".prr", ".txt")):
        if not node.startswith(("lib:", "case:", "data:")) and not pathlib.Path(node).is_absolute():
            return str((base / node).resolve())
    return node


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case_path: pathlib.Path, out: pathlib.Path) -> tuple[str, float]:
    case = load_vehicle_case(case_path)
    started = time.perf_counter()
    result = simulate_vehicle(case)
    elapsed = time.perf_counter() - started
    out.mkdir(parents=True, exist_ok=True)
    history_path, _manifest = save_vehicle_result(case, result, out)
    return sha256(pathlib.Path(history_path)), elapsed


def derive(base: pathlib.Path, *, duration_s: float, x_start_m: float) -> pathlib.Path:
    """Same case with a constant speed profile restating the declared speed."""

    raw = json.loads(base.read_text(encoding="utf-8"))
    speed = float(raw["vehicle"]["travel_speed_m_s"])
    raw["run"].update({"x_start_m": x_start_m, "duration_s": duration_s,
                       "output_step_s": duration_s / 100.0})
    raw["run"]["speed_profile"] = {"constant": {"speed_m_s": speed, "duration_s": duration_s}}
    raw.pop("initial_state", None)
    raw = absolutise(raw, base.parent)
    raw["case_id"] = f"{raw.get('case_id', 'case')}_constant_profile"
    target = WORK / f"case_{raw['case_id']}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(raw, indent=1, ensure_ascii=False), encoding="utf-8")
    return target


def main() -> int:
    rows = []
    failures = 0
    for label, name, duration_s, x_start_m in CASES:
        base = data_root.case_dir() / name
        declared = json.loads(base.read_text(encoding="utf-8"))
        declared["run"].update({"x_start_m": x_start_m, "duration_s": duration_s,
                                "output_step_s": duration_s / 100.0})
        declared = absolutise(declared, base.parent)
        declared.pop("initial_state", None)
        declared_path = WORK / f"case_{label}_declared.json"
        declared_path.parent.mkdir(parents=True, exist_ok=True)
        declared_path.write_text(json.dumps(declared, indent=1, ensure_ascii=False), encoding="utf-8")
        profile_path = derive(base, duration_s=duration_s, x_start_m=x_start_m)

        first, seconds_first = run(declared_path, WORK / f"out_{label}_declared")
        second, seconds_second = run(profile_path, WORK / f"out_{label}_profile")
        same = first == second
        failures += 0 if same else 1
        rows.append((label, first, second, same, seconds_first, seconds_second))
        print(f"{label:18s} {first[:16]} {second[:16]} "
              f"{'IDENTICAL' if same else 'DIFFERENT':9s} {seconds_first:6.1f} s / {seconds_second:6.1f} s")

    report = [{"case": row[0], "declared_sha256": row[1], "profile_sha256": row[2],
               "identical": row[3], "seconds": [row[4], row[5]]} for row in rows]
    (WORK / "equivalence.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    verdict = "EQUIVALENT" if failures == 0 else f"BROKEN ({failures} of {len(rows)})"
    print(f"VERDICT: {verdict}")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
