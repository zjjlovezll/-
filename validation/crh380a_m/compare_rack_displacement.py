"""Displacement family: the one comparison that is dimensionally closed today.

Measured CH13 (vertical displacement in the crossing area) is a millimetre reading of a rail
that moves on its supports, so it is directly comparable with the *rail body* vertical motion of
the simulation once both sides are de-trended against the same distance axis (the track falls at
12 %, so raw z carries 60 mm of grade over 0.5 m and must be removed before any amplitude is read).
"""

from __future__ import annotations

import json
from pathlib import Path

import h5py
import numpy as np

from velch.io.measured import lowpass

OUTPUT = Path(r"H:\齿轨工况\坡度工况\matlab\VEH_GEAR0_FX_STR_RACKN_QY-Re1_cjy_whcl_zn_TE_USERFORCE_CG_120.output")
PLAIN = OUTPUT / "NoExt_zgzn_jdz6.2mm_SP_00.mat"
BASE = Path(__file__).resolve().parent

# published campaign statistics for the same crossing-area gauge, 30 km/h up-slope
MEASURED_CH13 = {"peak_to_peak_mm": 2.075, "p999_mm": 1.8225, "rms_mm": 0.5295}


def vector(group: h5py.Group, axis: str) -> np.ndarray | None:
    if axis not in group:
        return None
    node = group[axis]
    if isinstance(node, h5py.Dataset):
        return np.asarray(node[...], float).ravel()
    if "values" in node:
        return np.asarray(node["values"][...], float).ravel()
    return None


def stats(residual: np.ndarray) -> dict[str, float]:
    return {
        "peak_to_peak_mm": float(residual.max() - residual.min()) * 1e3,
        "p999_mm": float(np.percentile(np.abs(residual - residual.mean()), 99.9)) * 1e3,
        "rms_mm": float(np.sqrt(np.mean((residual - residual.mean()) ** 2))) * 1e3,
    }


def main() -> int:
    rows: list[dict[str, object]] = []
    with h5py.File(PLAIN, "r") as handle:
        time_s = vector(handle["timeInt"], "time")
        bodies = handle["timeInt/bodyPosTrans"]
        for name in sorted(bodies.keys()):
            node = bodies[name]
            if not isinstance(node, h5py.Group):
                continue
            if not any(token in name for token in ("Rail", "Sleeper", "WS")):
                continue
            x_m = vector(node, "x")
            z_m = vector(node, "z")
            if x_m is None or z_m is None:
                continue
            finite = np.isfinite(x_m) & np.isfinite(z_m)
            if finite.sum() < 10:
                continue
            x_m, z_m = x_m[finite], z_m[finite]
            if float(np.ptp(x_m)) <= 0.0:
                continue  # a body that never travels (rail/sleeper travel with the wheel only)
            slope, intercept = np.polyfit(x_m, z_m, 1)
            residual = z_m - (slope * x_m + intercept)
            if not np.isfinite(residual).all():
                continue
            step = float(np.median(np.diff(time_s))) if time_s is not None else 0.0
            filtered = (lowpass(residual, 1.0 / step, 10.0)
                        if step > 0.0 else residual)
            row = {"body": name, "grade": slope, **stats(residual),
                   "filtered_10hz": stats(filtered)}
            rows.append(row)
            smoothed = row["filtered_10hz"]  # type: ignore[index]
            print(f"{name:<34} grade {slope:+7.4f}  p-p {row['peak_to_peak_mm']:7.3f} mm  "
                  f"p99.9 {row['p999_mm']:6.3f}  rms {row['rms_mm']:6.3f}   "
                  f"[10 Hz] p-p {smoothed['peak_to_peak_mm']:7.3f} "
                  f"p99.9 {smoothed['p999_mm']:6.3f} rms {smoothed['rms_mm']:6.3f}")

    print(f"\nmeasured CH13 (30 km/h up-slope, crossing area): "
          f"p-p {MEASURED_CH13['peak_to_peak_mm']:.3f} mm  "
          f"p99.9 {MEASURED_CH13['p999_mm']:.3f}  rms {MEASURED_CH13['rms_mm']:.3f}")
    (BASE / "rack_displacement_compare.json").write_text(
        json.dumps({"simulated": rows, "measured_ch13": MEASURED_CH13},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
