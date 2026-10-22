"""Full 1.2 s runs for the two most promising fastener tunings.

The frog window cannot answer the band questions: its 0.05 s spectrum is a local
value, while the Simpack reference bands (1.09 / 4.84 kN rms) are full-run values
over 13.5-130 m. Only full runs are comparable, so compare full with full.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

BASE = pathlib.Path(__file__).resolve().parent
SOURCE = BASE / "case_Z_full_local_rail.json"
ENGINE = pathlib.Path(__file__).resolve().parents[2]

VARIANTS = [
    ("cz20", {"k_y_n_m": 30e6, "c_y_n_s_m": 20e3, "k_z_n_m": 50e6, "c_z_n_s_m": 20e3}),
    ("kz100", {"k_y_n_m": 30e6, "c_y_n_s_m": 20e3, "k_z_n_m": 100e6, "c_z_n_s_m": 20e3}),
]


def main() -> int:
    for tag, support in VARIANTS:
        raw = json.loads(SOURCE.read_text(encoding="utf-8"))
        raw["case_id"] = f"crh380a_m_z_full_{tag}"
        for template in raw["rail_templates"]:
            template["support"] = support
        path = BASE / f"case_Z_full_{tag}.json"
        path.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"== {tag}", flush=True)
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle", str(path),
             "--output", str(BASE / f"out_Z_full_{tag}")],
            cwd=ENGINE, capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": str(ENGINE / "src")},
        )
        if result.returncode != 0:
            print("   FAILED:", (result.stdout + result.stderr).strip()[-500:], flush=True)
            continue
        summary = json.loads((BASE / f"out_Z_full_{tag}" / "manifest.json")
                             .read_text(encoding="utf-8"))["summary"]
        print(f"   {summary['result_status']}  peak "
              f"{max(summary['peak_normal_force_n'].values()) / 1e3:.2f} kN", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
