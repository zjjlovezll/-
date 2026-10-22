"""Is the rail settlement (the measured CH13 counterpart) informative about pad stiffness?

Measured campaigns record *rail displacement* (CH13 at the crossing), not contact force, so the
observable a real inversion will have is settlement.  This script asks how strongly our own
settlement responds to the pad stiffness ``k_z`` and derives the resulting resolution, so that
when unfiltered data arrives we know what it can and cannot constrain.

Note the column-naming trap: in ``history.csv`` the track DOF are written as
``axle<k>_<left|right>_z_m`` (the *rail* vertical displacement), while ``axle<k>_z_m`` is the
*wheelset* vertical position.  This script reads the rail one.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from velch.io.history import read_history

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "case_frog_strip_soft.json"
WORK = Path(r"F:\velch_tmp\settle")
SCALES = (0.7, 1.0, 1.4)
RAIL_Z = "axle1_right_z_m"
FORCE = "axle1_right_normal_n"
CH13_MEASURED_MM = (1.557, 1.742, 1.990)


def run(scale: float) -> tuple[np.ndarray, np.ndarray, dict]:
    case = json.loads(SOURCE.read_text(encoding="utf-8"))
    case["case_id"] = f"settle_{scale:.2f}"
    for template in case["rail_templates"]:
        template["support"]["k_z_n_m"] *= scale
    path = BASE / f"case_settle_{scale:.2f}.json"
    path.write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")
    out = WORK / f"out_{scale:.2f}"
    subprocess.run([sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle", str(path),
                    "--output", str(out)], check=True, cwd=str(BASE.parent.parent.parent),
                   capture_output=True)
    table = read_history(out / "history.csv")
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    return (np.asarray(table[RAIL_Z], dtype=float), np.asarray(table[FORCE], dtype=float),
            manifest["summary"])


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    rows = []
    for scale in SCALES:
        rail_z, force, summary = run(scale)
        amplitude = float(rail_z.max() - rail_z.min())
        rows.append({"scale": scale, "amplitude_m": amplitude, "peak_force_n": float(force.max()),
                     "lost": int(np.count_nonzero(force <= 1e-9)),
                     "status": summary.get("result_status")})
        print(f"k_z x{scale:.2f}  rail-z excursion {amplitude * 1e3:7.3f} mm"
              f"  peak force {float(force.max()) / 1e3:6.2f} kN"
              f"  lost {int(np.count_nonzero(force <= 1e-9)):>2}  {summary.get('result_status')}")

    amplitudes = np.array([row["amplitude_m"] for row in rows], dtype=float)
    logs = np.log(np.array(SCALES, dtype=float))
    slope = float(np.polyfit(logs, np.log(amplitudes), 1)[0])
    print(f"\nd ln(rail-z excursion) / d ln(k_z) = {slope:+.4f}")
    reference = amplitudes[SCALES.index(1.0)]
    print(f"reference excursion {reference * 1e3:.3f} mm;"
          f" measured CH13 amplitude {CH13_MEASURED_MM} mm")

    # resolution: how much k_z change produces a settlement change equal to one sigma of a
    # plausible displacement measurement (0.01 mm, the campaign's own quiet-channel floor)
    sigma_m = 1.0e-5
    column = abs(slope) * reference  # d(amplitude)/d(ln k_z)
    resolution = sigma_m / column if column > 0 else float("inf")
    print(f"d(amplitude)/d(ln k_z) = {column * 1e3:.4f} mm per ln-unit")
    print(f"with sigma = {sigma_m * 1e3:.2f} mm -> sigma(ln k_z) = {resolution:+.4f} "
          f"({100.0 * resolution:+.2f} %)")

    payload = {"rows": rows, "log_slope": slope, "reference_m": reference,
               "measured_ch13_amplitude_mm": CH13_MEASURED_MM,
               "d_amplitude_d_ln_kz_mm": column * 1e3,
               "sigma_assumed_m": sigma_m, "resolution_ln": resolution,
               "rail_z_channel": RAIL_Z}
    (BASE / "settlement_observable.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
