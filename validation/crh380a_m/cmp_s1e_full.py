"""S1-e full-run comparison: Velch (with / without the 600 mm support compliance)
against the Simpack reference run in `350.mat`.

Both are the CRH380A_M at 350 km/h over the same 1.2 s window (2401 samples).
Only two physical quantities are compared: the front wheelset vertical position and
the right-rail normal force.
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

BASE = pathlib.Path(__file__).resolve().parent
SIMPACK = pathlib.Path(r"F:\ai道岔状态反演辨识\simpack-mcp-2021x\results"
                       r"\case_a47bc7d9e48f40b08628147bfab5c3f4\model.output\350.mat")
PAIR = "timeInt/forceForce/SS_F__S_WS_F__F_RWContact_RWP_R/z"
BODY = "timeInt/bodyPosTrans/SS_F__S_WS_F__B_WS/z"


def velch_row(directory: str) -> dict:
    root = BASE / directory
    history = np.genfromtxt(root / "history.csv", delimiter=",", names=True)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    summary = manifest["summary"]
    force = history["axle1_right_normal_n"]
    z = history["axle1_z_m"]
    time = history["time_s"]
    spectrum = np.fft.rfft(force - force.mean())
    freq = np.fft.rfftfreq(force.size, float(time[1] - time[0]))
    amplitude = 2.0 * np.abs(spectrum) / force.size
    band = lambda lo, hi: float(np.sqrt(np.sum(amplitude[(freq >= lo) & (freq <= hi)] ** 2)))
    return {
        "case": directory,
        "status": summary["result_status"],
        "peak_kn": float(force.max() / 1e3),
        "min_kn": float(force.min() / 1e3),
        "mean_kn": float(force.mean() / 1e3),
        "lost": int(np.sum(force <= 0.0)),
        "max_pen_mm": summary["max_penetration_m"] * 1e3,
        "max_hertz_mm": summary.get("max_hertz_penetration_m", float("nan")) * 1e3,
        "max_settle_mm": summary.get("max_support_settlement_m", float("nan")) * 1e3,
        "wheel_z_pp_mm": float(np.ptp(z)) * 1e3,
        "dominant_hz": float(freq[int(np.argmax(amplitude[1:])) + 1]),
        "rms_150_250_kn": band(150.0, 250.0) / 1e3,
        "rms_30_60_kn": band(30.0, 60.0) / 1e3,
        "samples": int(force.size),
    }


def simpack_row() -> dict | None:
    try:
        import h5py
    except ImportError:
        return None
    if not SIMPACK.exists():
        return None
    with h5py.File(SIMPACK, "r") as handle:
        force = np.asarray(handle[PAIR]["values"]).ravel()
        z = np.asarray(handle[BODY]["values"]).ravel()
    spectrum = np.fft.rfft(force - force.mean())
    step = 1.2 / (force.size - 1)
    freq = np.fft.rfftfreq(force.size, step)
    amplitude = 2.0 * np.abs(spectrum) / force.size
    band = lambda lo, hi: float(np.sqrt(np.sum(amplitude[(freq >= lo) & (freq <= hi)] ** 2)))
    return {
        "case": "Simpack 350.mat",
        "status": "reference",
        "peak_kn": float(force.max() / 1e3),
        "min_kn": float(force.min() / 1e3),
        "mean_kn": float(force.mean() / 1e3),
        "lost": int(np.sum(force <= 0.0)),
        "max_pen_mm": float("nan"),
        "max_hertz_mm": float("nan"),
        "max_settle_mm": float("nan"),
        "wheel_z_pp_mm": float(np.ptp(z)) * 1e3,
        "dominant_hz": float(freq[int(np.argmax(amplitude[1:])) + 1]),
        "rms_150_250_kn": band(150.0, 250.0) / 1e3,
        "rms_30_60_kn": band(30.0, 60.0) / 1e3,
        "samples": int(force.size),
    }


def main() -> int:
    rows = []
    for directory in ("out_Y_base", "out_Y_support", "out_Z_full_local_rail",
                       "out_Z_full_cz20", "out_Z_full_kz100",
                       "out_W_full_series199"):
        try:
            rows.append(velch_row(directory))
        except FileNotFoundError:
            print(f"missing {directory}")
    reference = simpack_row()
    if reference:
        rows.append(reference)
    header = ("case", "status", "peak_kn", "min_kn", "mean_kn", "lost", "max_pen_mm",
              "max_hertz_mm", "max_settle_mm", "wheel_z_pp_mm", "dominant_hz",
              "rms_150_250_kn", "rms_30_60_kn")
    widths = {"case": 18, "status": 22}
    print("  ".join(f"{h:>{widths.get(h, 13)}s}" for h in header))
    for row in rows:
        cells = []
        for key in header:
            value = row[key]
            if isinstance(value, float):
                cells.append(f"{value:13.4f}")
            else:
                cells.append(f"{str(value):>{widths.get(key, 13)}s}")
        print("  ".join(cells))
    out = BASE / "s1e_full_ab.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("written", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
