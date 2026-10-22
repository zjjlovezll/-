"""S2 acceptance: BDF+analytic vs the frozen DOP853 full run, on the same numbers."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent
OUT = Path("F:/velch_tmp/s2")
CANDIDATES = [
    ("dop853 frozen", BASE / "out_full12_cap05"),
    ("bdf an rtol1e-5", OUT / "s2_full_bdf_an_rtol1e-5"),
    ("bdf an rtol1e-6", OUT / "s2_full_bdf_an_rtol1e-6"),
]


def load(directory: Path) -> dict[str, object] | None:
    manifest = directory / "manifest.json"
    history = directory / "history.csv"
    if not manifest.exists() or not history.exists():
        return None
    raw = json.loads(manifest.read_text(encoding="utf-8"))
    summary = raw.get("summary", {})
    header = history.read_text(encoding="utf-8").splitlines()[0].split(",")
    data = np.loadtxt(history, delimiter=",", skiprows=1)
    columns = {name: data[:, index] for index, name in enumerate(header)}
    lost = 0
    deepest = 0.0
    for name, series in columns.items():
        if name.startswith("axle1_") and name.endswith("_normal_n"):
            lost += int(np.count_nonzero(series <= 0.0))
        if name.endswith("_penetration_m"):
            deepest = max(deepest, float(np.max(series)))
    travel = float(np.ptp(columns["axle1_z_m"])) * 1e3 if "axle1_z_m" in columns else float("nan")
    return {
        "status": summary.get("result_status"),
        "nfev": summary.get("nfev"),
        "peak_kn": float(summary.get("peak_normal_force_n", {}).get("axle1_right", 0.0)) / 1e3,
        "maxpen_um": deepest * 1e6,
        "lost_axle1": lost,
        "travel_mm": travel,
        "samples": int(data.shape[0]),
    }


def main() -> int:
    print(f"{'run':>18}{'status':>24}{'nfev':>9}{'peak kN':>9}"
          f"{'maxpen um':>11}{'lost':>6}{'travel mm':>11}{'N':>7}")
    for label, directory in CANDIDATES:
        row = load(directory)
        if row is None:
            continue
        print(f"{label:>18}{str(row['status']):>24}{str(row['nfev']):>9}"
              f"{row['peak_kn']:>9.2f}{row['maxpen_um']:>11.2f}{row['lost_axle1']:>6d}"
              f"{row['travel_mm']:>11.3f}{row['samples']:>7d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
