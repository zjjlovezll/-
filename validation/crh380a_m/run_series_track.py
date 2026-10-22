"""S1-f: the missing layer is the sleeper on the ballast, not the rail beam.

Finding from `build_rail_modes.py`: a 60 kg/m rail on 25e6 N/m fasteners has its
*first* mode at 132 Hz (uniform heave on the pads, sqrt(k_pad/m_bay) = sqrt(25e6/36.4)),
so a rail beam cannot supply any 30-60 Hz content. The band has to come from the
layer below: sleeper mass on the ballast.

Series estimate (SDITT Flexible Track: ballast kz 20e6 N/m per metre, 0.6 m bay ->
12e6 N/m per bay; sleeper 131.6 kg/m -> 79 kg per bay; rail 2 m of 60 kg/m -> 121 kg):
    k_series = 1/(1/25e6 + 1/12e6) = 8.11e6 N/m
    f        = sqrt(k_series / (121 + 79)) / 2/pi = sqrt(8.11e6/200)/2/pi = 32.0 Hz
which is Simpack's 31.65 Hz. So the two-mass (rail + sleeper) chain is the mechanism.

This script tests the lumped 1-DOF equivalent of that chain (rail+sleeper mass on the
series stiffness) on the frog window, then the best variant on the full 1.2 s run.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

BASE = pathlib.Path(__file__).resolve().parent
ENGINE = pathlib.Path(__file__).resolve().parents[2]
WINDOW = BASE / "case_Z_local_rail.json"
FULL = BASE / "case_Z_full_local_rail.json"

VARIANTS = [
    # tag, rail mass, support
    ("series120", 120.0, {"k_y_n_m": 30e6, "c_y_n_s_m": 30e3, "k_z_n_m": 8.11e6, "c_z_n_s_m": 30e3}),
    ("series199", 199.0, {"k_y_n_m": 30e6, "c_y_n_s_m": 30e3, "k_z_n_m": 8.11e6, "c_z_n_s_m": 30e3}),
    ("pad_only_199", 199.0, {"k_y_n_m": 30e6, "c_y_n_s_m": 30e3, "k_z_n_m": 50e6, "c_z_n_s_m": 20e3}),
]


def build(source: pathlib.Path, name: str, tag: str, mass: float, support: dict) -> pathlib.Path:
    raw = json.loads(source.read_text(encoding="utf-8"))
    raw["case_id"] = f"crh380a_m_{tag}"
    raw["track_dynamics"] = {"kind": "local_compliant"}
    for template in raw["rail_templates"]:
        template["mass_y_kg"] = mass
        template["mass_z_kg"] = mass
        template["support"] = support
    path = BASE / name
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def run(path: pathlib.Path, output: pathlib.Path) -> dict | None:
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle", str(path),
         "--output", str(output)],
        cwd=ENGINE, capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(ENGINE / "src")},
    )
    if result.returncode != 0:
        print("   FAILED:", (result.stdout + result.stderr).strip()[-400:], flush=True)
        return None
    return json.loads((output / "manifest.json").read_text(encoding="utf-8"))["summary"]


def main() -> int:
    for tag, mass, support in VARIANTS:
        path = build(WINDOW, f"case_W_{tag}.json", f"w_{tag}", mass, support)
        print(f"== window {tag}  mass {mass}  kz {support['k_z_n_m']:.3g}", flush=True)
        summary = run(path, BASE / f"out_W_{tag}")
        if summary:
            print(f"   {summary['result_status']}  peak "
                  f"{max(summary['peak_normal_force_n'].values()) / 1e3:.2f} kN  "
                  f"pen {summary['max_penetration_m'] * 1e3:.3f} mm", flush=True)
    tag, mass, support = VARIANTS[1]
    path = build(FULL, f"case_W_full_{tag}.json", f"w_full_{tag}", mass, support)
    print(f"== full 1.2 s {tag}", flush=True)
    summary = run(path, BASE / f"out_W_full_{tag}")
    if summary:
        print(f"   {summary['result_status']}  peak "
              f"{max(summary['peak_normal_force_n'].values()) / 1e3:.2f} kN", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
