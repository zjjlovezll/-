"""检查右轨在「直向接触带」内的走行面沿里程的形状。

目的：在动手平滑之前，先量化要被平滑的东西——
h(s) = 该站位在接触带 y∈[y_lo, y_hi] 上最高的轨面 z（绝对标高），
以及它沿里程的梯度。轮子在这一带内能获得的支撑就是 h(s)。
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np

BASE = r"F:\ai道岔状态反演辨识\Velch\validation\crh380a_m"
CASE = os.path.join(BASE, "case_C_bodies.json")


def load_csv_points(path: str) -> tuple[np.ndarray, np.ndarray, float]:
    rows = []
    for line in open(path, encoding="utf-8"):
        parts = line.replace(",", " ").split()
        if len(parts) < 2:
            continue
        try:
            rows.append((float(parts[0]), float(parts[1])))
        except ValueError:
            continue
    arr = np.asarray(rows, dtype=float)
    # 位置参数单位：main/point 的 CSV 是 mm；prr 是 m（由调用方判断）
    return arr[:, 0], arr[:, 1], 0.0


def station_profile(profile: dict, base: str) -> tuple[np.ndarray, np.ndarray]:
    path = os.path.join(base, profile["file"])
    units = profile.get("units", "m")
    y, z, _ = load_csv_points(path)
    scale = 1e-3 if units == "mm" else 1.0
    y = y * scale
    z = z * scale
    y_sign = int(profile.get("y_sign", 1))
    z_sign = int(profile.get("z_sign", 1))
    y = y * y_sign + float(profile.get("y_offset_m", 0.0))
    z = z * z_sign + float(profile.get("z_offset_m", 0.0))
    order = np.argsort(y)
    return y[order], z[order]


def main() -> None:
    case = json.load(open(CASE, encoding="utf-8"))
    tpl = [t for t in case["rail_templates"] if t["id"] == "right"][0]
    y_lo = float(sys.argv[1]) if len(sys.argv) > 1 else 0.735
    y_hi = float(sys.argv[2]) if len(sys.argv) > 2 else 0.760

    rows = []
    for body in tpl["bodies"]:
        for st in body["stations"]:
            s = float(st["s_m"])
            if not (78.0 <= s <= 82.2):
                continue
            y, z = station_profile(st["profile"], BASE)
            m = (y >= y_lo) & (y <= y_hi)
            if not np.any(m):
                rows.append((s, body["id"], np.nan, np.nan, 0))
                continue
            k = int(np.argmax(z[m]))
            rows.append((s, body["id"], float(z[m][k]), float(y[m][k]), int(m.sum())))

    # 每个站位取各轨体中的最高面
    by_s: dict[float, list] = {}
    for s, bid, z, y, n in rows:
        by_s.setdefault(round(s, 6), []).append((bid, z, y, n))
    stations = sorted(by_s)
    print(f"接触带 y∈[{y_lo*1000:.1f},{y_hi*1000:.1f}] mm，站位数 {len(stations)}")
    print("   s_m      h(mm)     y(mm)   body      dh/ds(mm/m)")
    prev = None
    for s in stations:
        best = max(by_s[s], key=lambda t: (t[1] if np.isfinite(t[1]) else -1e9))
        bid, z, y, n = best
        if not np.isfinite(z):
            print(f"  {s:8.4f}     无覆盖")
            continue
        g = (z - prev[0]) / (s - prev[1]) * 1e3 if prev and s > prev[1] else np.nan
        print(f"  {s:8.4f}  {z*1e3:9.4f}  {y*1e3:9.3f}  {bid:6s}  "
              f"{'' if np.isnan(g) else f'{g:12.3f}'}")
        prev = (z, s)


if __name__ == "__main__":
    main()
