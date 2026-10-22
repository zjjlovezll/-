"""Overlay our wheelset vertical trajectory with Simpack's, frog window.

Both quantities are the *same physical thing*: the height of the front wheelset
centre.  Ours comes from ``history.csv`` (``axle1_z_m`` is the absolute height,
the case starts the wheel at the nominal radius), Simpack's from the ``350.mat``
body channel ``SS_F__S_WS_F__B_WS/z`` (absolute, negative below the origin).

The comparison is the honest test of "is our geometry the same": if our wheel
falls ~1.2 mm where Simpack's falls 0.6 mm, the extra fall is the geometric
difference, and the force difference follows from it.

Usage: python cmp_trajectory.py [our_out_dir] [png]
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT.parent / "simpack-mcp-2021x" / "src"))

MAT = (ROOT.parent / "simpack-mcp-2021x" / "results"
       / "case_a47bc7d9e48f40b08628147bfab5c3f4" / "model.output" / "350.mat")
GROUP = "timeInt/RS_result/SRS_S_R/SRS_S_WS_F/SRS_RWP_R/SRS_RWP_R_Pair"
BODY = "timeInt/bodyPosTrans/SS_F__S_WS_F__B_WS"


def simpack_track():
    import h5py  # noqa: PLC0415

    with h5py.File(MAT, "r") as handle:
        # Take the longitudinal position from the same body element as z, so the
        # two series are guaranteed to be the same object.
        s = np.asarray(handle[f"{BODY}/x/values"]).ravel()
        z = np.asarray(handle[f"{BODY}/z/values"]).ravel()
    return s, z


def our_track(out_dir: Path):
    rows = list(csv.DictReader(open(out_dir / "history.csv", encoding="utf-8")))
    s = np.array([float(r["axle1_x_m"]) for r in rows])
    z = np.array([float(r["axle1_z_m"]) for r in rows])
    return s, z


def main(argv: list[str]) -> int:
    out_dir = Path(argv[1]) if len(argv) > 1 else BASE / "out_wing_frog_0p05s"
    png = Path(argv[2]) if len(argv) > 2 else BASE / "out_wing_vs_simpack_z.png"
    s_sim, z_sim = simpack_track()
    s_our, z_our = our_track(out_dir)
    lo = max(s_sim.min(), s_our.min())
    hi = min(s_sim.max(), s_our.max())
    grid = np.arange(lo, hi, 0.01)
    zs = np.interp(grid, s_sim, z_sim)
    zo = np.interp(grid, s_our, z_our)
    print(f"window {lo:.2f}..{hi:.2f} m  {grid.size} samples")
    print(f"  Simpack z p-p {np.ptp(zs) * 1e3:.3f} mm  min {zs.min() * 1e3:.3f} max {zs.max() * 1e3:.3f}")
    print(f"  Velch   z p-p {np.ptp(zo) * 1e3:.3f} mm  min {zo.min() * 1e3:.3f} max {zo.max() * 1e3:.3f}")
    delta = zo - zs
    print(f"  delta  mean {delta.mean() * 1e3:+.3f} mm  p-p {np.ptp(delta) * 1e3:.3f} mm  "
          f"max |d| {np.abs(delta).max() * 1e3:.3f} mm")

    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    axes[0].plot(grid, (zs - zs.mean()) * 1e3, label="Simpack", color="#d8843a")
    axes[0].plot(grid, (zo - zo.mean()) * 1e3, label="Velch (wing body)", color="#2f6f9e")
    axes[0].set_ylabel("wheelset z - mean  (mm)")
    axes[0].legend()
    axes[0].grid(alpha=0.3)
    axes[0].set_title("CRH380A_M 350 km/h: front wheelset vertical trajectory, frog window")
    axes[1].plot(grid, (zo - zs) * 1e3, color="#3c8c5a")
    axes[1].set_ylabel("Velch - Simpack  (mm)")
    axes[1].set_xlabel("longitudinal position x (m)")
    axes[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(png, dpi=150)
    print(f"  figure {png}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
