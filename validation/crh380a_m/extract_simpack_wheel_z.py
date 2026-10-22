"""从 Simpack 的 .mat 结果里取「前轮对竖向行程 + 左右接触力」，用于回答
“同一套 PRR，为什么 Simpack 不出现 600 kN”。

用法： python extract_simpack_wheel_z.py <350.mat> [x_lo] [x_hi]
"""

from __future__ import annotations

import sys

import h5py
import numpy as np

MAT = (
    r"F:\ai道岔状态反演辨识\simpack-mcp-2021x\results"
    r"\case_a47bc7d9e48f40b08628147bfab5c3f4\model.output\350.mat"
)
GROUP_WS = "bodyPosTrans/SS_F__S_WS_F__B_WS"
GROUP_FL = "forceForce/SS_F__S_WS_F__F_RWContact_RWP_L"
GROUP_FR = "forceForce/SS_F__S_WS_F__F_RWContact_RWP_R"


def series(ti, path: str) -> np.ndarray:
    return np.asarray(ti[path]["values"][0], dtype=float)


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else MAT
    lo = float(sys.argv[2]) if len(sys.argv) > 2 else 77.0
    hi = float(sys.argv[3]) if len(sys.argv) > 3 else 84.5

    with h5py.File(path, "r") as f:
        ti = f["timeInt"]
        x = series(ti, GROUP_WS + "/x")
        z = series(ti, GROUP_WS + "/z")
        y = series(ti, GROUP_WS + "/y")
        fl = series(ti, GROUP_FL + "/z")
        fr = series(ti, GROUP_FR + "/z")

    print(f"samples={len(x)}  x={x[0]:.3f}..{x[-1]:.3f} m")
    print(f"轮对竖向 z: min={z.min():.6f} max={z.max():.6f} "
          f"峰峰={np.ptp(z) * 1e3:.4f} mm")
    print(f"轮对横向 y: min={y.min():.6f} max={y.max():.6f} "
          f"峰峰={np.ptp(y) * 1e3:.4f} mm")
    print(f"接触力 L: {fl.min()/1e3:.2f}..{fl.max()/1e3:.2f} kN   "
          f"R: {fr.min()/1e3:.2f}..{fr.max()/1e3:.2f} kN")

    sel = (x > lo) & (x < hi)
    base = z[sel].mean()
    print("\n    x_m      wheel_z(mm rel)   F_left_kN  F_right_kN")
    for i in np.where(sel)[0][::10]:
        print(f"  {x[i]:7.3f}  {(z[i]-base)*1e3:14.5f}  "
              f"{fl[i]/1e3:10.2f}  {fr[i]/1e3:10.2f}")


if __name__ == "__main__":
    main()
