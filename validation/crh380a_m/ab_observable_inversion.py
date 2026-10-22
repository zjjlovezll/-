"""Does the waveform make the fastener parameters separable where the peak did not?

Re-runs the 20 ms inversion window with +-10 % on one parameter at a time (the other held
fixed), builds central-difference columns of the right-rail normal-force waveform, and asks
the identifiability gate what it can separate. Prints both the waveform verdict and the
peak-only verdict for contrast.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from velch.inverse.identifiability import Sensitivity, analyse
from velch.io.history import read_history

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "case_inverse_window.json"
WORK = Path(r"F:\velch_tmp\obs")
CHANNEL = "axle1_right_normal_n"
NOISE = 1.0e3
SCALES = (0.9, 1.1)
SPAN = np.log(1.1) - np.log(0.9)
PARAMS = (("rail_k_z", "support", "k_z_n_m"), ("rail_c_z", "support", "c_z_n_s_m"))


def run(case: dict, name: str) -> np.ndarray:
    case = json.loads(json.dumps(case))
    case["case_id"] = name
    path = BASE / f"obsdiff_{name}.json"
    path.write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")
    out = WORK / f"out_{name}"
    subprocess.run([sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle", str(path),
                    "--output", str(out)], check=True, cwd=str(BASE.parent.parent.parent),
                   capture_output=True)
    table = read_history(out / "history.csv")
    return np.asarray(table[CHANNEL], dtype=float)


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    base = json.loads(SOURCE.read_text(encoding="utf-8"))
    reference = run(base, "obs_base")
    count = reference.size
    print(f"baseline samples {count}  peak {reference.max() / 1e3:.1f} kN")

    columns, peak_columns = [], []
    for name, block, key in PARAMS:
        waveforms = {}
        for scale in SCALES:
            case = json.loads(json.dumps(base))
            for template in case["rail_templates"]:
                template[block][key] *= scale
            waveforms[scale] = run(case, f"{name}_{scale:.1f}")
        difference = (waveforms[SCALES[1]] - waveforms[SCALES[0]]) / SPAN
        columns.append(-difference)
        peak_columns.append(np.array([-(waveforms[SCALES[1]].max()
                                       - waveforms[SCALES[0]].max()) / SPAN]))
        print(f"{name:<10} column norm {np.linalg.norm(difference):10.1f} N/ln-unit")

    names = tuple(name for name, _, _ in PARAMS)
    for label, matrix, rows in (
        ("waveform", np.column_stack(columns), count),
        ("peak", np.column_stack(peak_columns), 1),
    ):
        verdict = analyse(Sensitivity(names, matrix, (NOISE,) * rows, observable=label))
        print(f"\n--- {label} ---")
        print(verdict.summary())
        for note in verdict.notes:
            print(f"  note: {note}")
        for name in names:
            value = verdict.resolution[name]
            print(f"  {name:<10} sigma(ln) per 1 kN = {value:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
