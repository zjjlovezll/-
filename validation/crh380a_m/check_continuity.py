"""检查"断面沿里程是否连续"：给出每个算例在指定横向列上的 z(s)、坡度及其跳变。

用法（在 Velch 目录下运行）:
    python -X utf8 validation/crh380a_m/check_continuity.py case_C_bodies.json case_F_smooth_all.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from velch.vehicle import load_vehicle_case

BASE = Path(__file__).resolve().parent
ROWS = (0.7530, 0.7440)  # 翼轨带 / 心轨带


def column(series, s_grid: np.ndarray, y_m: float) -> np.ndarray:
    out = np.full(s_grid.size, np.nan)
    for k, s_m in enumerate(s_grid):
        try:
            sample = series.sample(float(s_m), 1)
        except Exception:
            continue
        prof = sample.profile
        y = np.asarray(prof.y_m, dtype=float)
        z = np.asarray(prof.z_m, dtype=float)
        if y.size < 2 or y_m < y[0] or y_m > y[-1]:
            continue
        out[k] = float(np.interp(y_m, y, z))
    return out


def station_grid(case_path: Path) -> list[float]:
    case = json.loads(case_path.read_text(encoding="utf-8"))
    tpl = [t for t in case["rail_templates"] if t["id"] == "right"][0]
    stations: list[float] = []
    for body in tpl.get("bodies") or [tpl]:
        stations += [float(st["s_m"]) for st in body["stations"]]
    return sorted(set(stations))


def main() -> None:
    for arg in sys.argv[1:]:
        path = BASE / arg
        s_all = np.array(station_grid(path))
        sel = s_all[(s_all >= 79.0) & (s_all <= 81.5) & np.isfinite(s_all)]
        case = load_vehicle_case(path)
        rail = [r for r in case.rails if r.id.endswith("_right")][0]
        print(f"\n=== {arg}  右轨 {len(s_all)} 站位，辙叉段 {len(sel)} 站位 ===")
        if len(sel) > 2:
            d = np.diff(sel) * 1e3
            print(f"    相邻站距: min {d.min():.2f} / 中位 {np.median(d):.2f} / max {d.max():.2f} mm")
        for body in rail.contact_bodies:
            for y_m in ROWS:
                z = column(body.series, sel, y_m)
                good = np.isfinite(z)
                if good.sum() < 3:
                    continue
                ss, zz = sel[good], z[good]
                dst = np.diff(ss)
                if np.any(dst <= 0):
                    continue
                slope = np.diff(zz) / dst * 1e3
                jump = np.abs(np.diff(slope)) if slope.size > 1 else np.zeros(1)
                print(f"    [{body.id:5s}] y={y_m*1e3:6.1f} mm  "
                      f"z {zz.min()*1e3:8.3f}..{zz.max()*1e3:8.3f} mm  "
                      f"|dh/ds|max {np.abs(slope).max():7.3f} mm/m  "
                      f"坡度跳变 max {float(jump.max()):7.3f} mm/m")

        # 支撑面 h(s)：接触带内的最高轨面——这是轮子真正踩的东西，不受横向迁移混淆
        band = (0.735, 0.760)
        h = np.full(sel.size, np.nan)
        for k, s_m in enumerate(sel):
            best = -np.inf
            for body in rail.contact_bodies:
                try:
                    prof = body.series.sample(float(s_m), 1).profile
                except Exception:
                    continue
                y = np.asarray(prof.y_m, dtype=float)
                z = np.asarray(prof.z_m, dtype=float)
                m = (y >= band[0]) & (y <= band[1])
                if np.any(m):
                    best = max(best, float(z[m].max()))
            if np.isfinite(best):
                h[k] = best * 1e3
        g = np.isfinite(h)
        if g.sum() >= 3:
            hh, ss = h[g], sel[g]
            ds = np.diff(ss)
            sl = np.diff(hh) / ds  # mm/m
            jmp = np.abs(np.diff(sl)) if sl.size > 1 else np.zeros(1)
            print(f"    [支撑面]          h {hh.min():8.3f}..{hh.max():8.3f} mm  "
                  f"|dh/ds|max {np.abs(sl).max():7.3f} mm/m  "
                  f"坡度跳变 max {float(jmp.max()):7.3f} mm/m")


if __name__ == "__main__":
    main()
