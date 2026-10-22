"""S1-e tuning: how much fastener damping does the rail DOF need?

The rail DOF already matches Simpack to 0.17% in wheel travel, but the 30-60 Hz band
is 41% low (2.84 vs 4.84 kN rms) while the 150-250 Hz band is already slightly
below Simpack (0.58 vs 1.09) -- i.e. we may be over-damping the fastener and
killing both bands. Sweep `c_z` (and one `k_z` pair) on the 0.05 s frog window.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

BASE = pathlib.Path(__file__).resolve().parent
SOURCE = BASE / "case_Z_local_rail.json"
ENGINE = pathlib.Path(__file__).resolve().parents[2]

VARIANTS = [
    ("cz10", {"c_z_n_s_m": 10e3, "k_z_n_m": 50e6}),
    ("cz20", {"c_z_n_s_m": 20e3, "k_z_n_m": 50e6}),
    ("cz40", {"c_z_n_s_m": 40e3, "k_z_n_m": 50e6}),
    ("cz80", {"c_z_n_s_m": 80e3, "k_z_n_m": 50e6}),
    ("kz25_cz20", {"c_z_n_s_m": 20e3, "k_z_n_m": 25e6}),
    ("kz100_cz20", {"c_z_n_s_m": 20e3, "k_z_n_m": 100e6}),
]


def build(tag: str, support: dict) -> pathlib.Path:
    raw = json.loads(SOURCE.read_text(encoding="utf-8"))
    raw["case_id"] = f"crh380a_m_z_{tag}"
    for template in raw["rail_templates"]:
        template["support"] = {"k_y_n_m": 30e6, "c_y_n_s_m": 20e3,
                               **support}
    path = BASE / f"case_Z_{tag}.json"
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main() -> int:
    for tag, support in VARIANTS:
        path = build(tag, support)
        print(f"== {tag}  {support}", flush=True)
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle", str(path),
             "--output", str(BASE / f"out_Z_{tag}")],
            cwd=ENGINE, capture_output=True, text=True,
            env={**__import__("os").environ, "PYTHONPATH": str(ENGINE / "src")},
        )
        if result.returncode != 0:
            print("   FAILED:", (result.stdout + result.stderr).strip()[-400:], flush=True)
            continue
        manifest = json.loads((BASE / f"out_Z_{tag}" / "manifest.json").read_text(encoding="utf-8"))
        summary = manifest["summary"]
        print(f"   {summary['result_status']}  peak "
              f"{max(summary['peak_normal_force_n'].values()) / 1e3:.2f} kN  "
              f"active {summary['active_output_samples']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
