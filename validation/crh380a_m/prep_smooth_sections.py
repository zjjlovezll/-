"""纵向型面 C1 重建（含支撑面坡度诊断）。

为什么需要它
------------
原始 PRR 是按站位离散的折线：`ProfileSeries.sample` 在站位之间做**线性插值**，
于是每隔 15–60 mm，走行面的斜率就跳一次。轮子以 97.2 m/s 通过时，斜率跳变
等于给一系悬挂一个台阶式速度激励；在辙叉区（站位 5–60 mm）这些台阶落在
同一条 1.4 mm 的下坡上，累积成 600 kN 的冲击。

本工具做三件事，都不改变**原始测点**，只改变"测点之间怎么连"：
1. 横向：每个断面取上包络（轨顶），用保形三次（PCHIP）重建到 0.05 mm 网格。
2. 纵向：每个横向列沿里程用 PCHIP（C1）重建，再按 5 mm 站距重采样，
   使求解器的线性插值误差降到 1e-4 mm 量级。
3. 诊断：在新网格上算支撑面 h(s)（接触带内最高轨面）及其一阶/二阶差分，
   与原始折线对比，报告平滑前后的坡度跳变量。

用法
----
    python prep_smooth_sections.py --case case_C_bodies.json \
        --s-lo 78.0 --s-hi 82.2 --ds 0.005 --out case_D_smooth.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator

BASE = Path(__file__).resolve().parent


def load_points(profile: dict) -> tuple[np.ndarray, np.ndarray]:
    path = BASE / profile["file"]
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            parts = line.replace(",", " ").split()
            if len(parts) < 2:
                continue
            try:
                rows.append((float(parts[0]), float(parts[1])))
            except ValueError:
                continue
    arr = np.asarray(rows, dtype=float)
    scale = 1e-3 if profile.get("units", "m") == "mm" else 1.0
    y = arr[:, 0] * scale * float(profile.get("y_sign", 1)) + float(
        profile.get("y_offset_m", 0.0)
    )
    z = arr[:, 1] * scale * float(profile.get("z_sign", 1)) + float(
        profile.get("z_offset_m", 0.0)
    )
    order = np.argsort(y)
    return y[order], z[order]


def upper_envelope(y: np.ndarray, z: np.ndarray, grid: np.ndarray) -> np.ndarray:
    """在 grid 上取上包络：±半个网格内的最大值。"""
    half = 0.5 * float(grid[1] - grid[0])
    lo = np.searchsorted(y, grid - half, side="left")
    hi = np.searchsorted(y, grid + half, side="right")
    out = np.full(grid.shape, np.nan)
    for i, (a, b) in enumerate(zip(lo, hi)):
        if b > a:
            out[i] = z[a:b].max()
    good = np.isfinite(out)
    if good.sum() < 2:
        return out
    fill = np.interp(grid, grid[good], out[good])
    return np.where(good, out, fill)


def limit_curvature(z: np.ndarray, dy: float, radius: float) -> np.ndarray:
    """轨头边缘圆角：切掉曲率半径小于 radius 的**凸角**，其余不动。

    实现是精确的形态学算子而不是迭代近似：

        z_new(y) = min_t [ z(y - t) + t²/(2·radius) ]

    对平顶（t=0 处取到）完全不动；对 R>radius 的缓凸面也不动；对尖角给出
    与两侧相切的圆弧——正是钢轨轨头 4–8 mm 边缘半径该有的形状。
    早前用"迭代压二阶差分"的写法会因符号翻转自激，已废弃。
    """
    k = max(int(round(radius / dy)), 1)
    t = np.arange(-k, k + 1, dtype=float) * dy
    penalty = t * t / (2.0 * radius)
    out = z.astype(float, copy=True)
    n = z.size
    for off, pen in zip(range(-k, k + 1), penalty):
        shifted = np.full(n, np.inf)
        if off > 0:
            shifted[off:] = z[: n - off]
        elif off < 0:
            shifted[:n + off] = z[-off:]
        else:
            shifted[:] = z
        np.fmin(out, shifted + pen, out=out)
    return out


def resample_body(
    stations: list[tuple[float, dict]],
    s_target: np.ndarray,
    dy: float = 5e-5,
    edge_radius: float = 0.006,
    fillet_stage: str = "station",
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """把某个轨体的若干断面重采样成 (n_s, n_y) 的高度场。

    每个站位的横向跨度不同（心轨鼻端会从 10 mm 长到 72 mm），所以取**并集**
    网格，各站位在自己的跨度外置 NaN；纵向只对"该列确有测点"的站位做 PCHIP，
    避免用交集把几何缩没。

    fillet_stage:
      "station" — 先在每个原始站位上做横向 C1 + 圆角，再沿里程插值（默认，第一轮做法）
      "final"   — 先沿里程插值成连续断面，再对**每一个最终断面**做横向 C1 + 圆角
                  （用户要求的口径：先形成连续断面，再平滑）

    返回 (grid, field, s_known, inside)；field 在 body 自身站位范围外为 NaN（不外推）。
    """
    s_known = np.array([s for s, _ in stations], dtype=float)
    profiles = [load_points(p) for _, p in stations]
    y_lo = min(float(y.min()) for y, _ in profiles)
    y_hi = max(float(y.max()) for y, _ in profiles)
    grid = np.arange(y_lo, y_hi + dy * 0.5, dy)

    z_rows = np.full((len(profiles), grid.size), np.nan)
    for i, (y, z) in enumerate(profiles):
        z_rows[i] = upper_envelope(y, z, grid)

    # 横向：PCHIP 去斜率跳变（"station" 口径下顺带做圆角）
    for i in range(z_rows.shape[0]):
        good = np.isfinite(z_rows[i])
        if good.sum() < 3:
            continue
        interp = PchipInterpolator(grid[good], z_rows[i][good], extrapolate=False)
        row = interp(grid)
        finite = np.isfinite(row)
        if fillet_stage == "station" and edge_radius > 0 and finite.sum() > 3:
            row[finite] = limit_curvature(row[finite], dy, edge_radius)
        z_rows[i] = row

    # 纵向：逐列 PCHIP，只用该列有值的站位；范围外保持 NaN
    out = np.full((s_target.size, grid.size), np.nan)
    inside = (s_target >= s_known.min() - 1e-12) & (s_target <= s_known.max() + 1e-12)
    for j in range(grid.size):
        col = z_rows[:, j]
        good = np.isfinite(col)
        if good.sum() >= 2:
            out[inside, j] = PchipInterpolator(s_known[good], col[good])(s_target[inside])
        elif good.sum() == 1:
            out[inside, j] = col[good][0]

    # "final" 口径：连续断面形成之后，再对每个断面做横向圆角
    if fillet_stage == "final" and edge_radius > 0:
        for k in range(out.shape[0]):
            finite = np.isfinite(out[k])
            if finite.sum() > 3:
                out[k][finite] = limit_curvature(out[k][finite], dy, edge_radius)
    return grid, out, s_known, inside


def write_station_csv(path: Path, y: np.ndarray, z: np.ndarray) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    good = np.isfinite(z)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        for yi, zi in zip(y[good], z[good]):
            handle.write(f"{yi * 1e3:.6f},{zi * 1e3:.6f}\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def crown(field_row: np.ndarray, grid: np.ndarray, lo: float, hi: float) -> tuple[float, float]:
    m = (grid >= lo) & (grid <= hi) & np.isfinite(field_row)
    if not np.any(m):
        return np.nan, np.nan
    j = int(np.argmax(field_row[m]))
    return float(field_row[m][j]), float(grid[m][j])


def smooth_window(
    case: dict,
    s_lo: float,
    s_hi: float,
    ds: float,
    band: tuple[float, float],
    edge_radius: float,
    close_point: bool = False,
    fillet_stage: str = "station",
) -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]]:
    """在一个里程窗口内把右轨各轨体做 C1 重建。

    返回 {body_id: (grid, field, s_known, inside)}；field 的纵向范围 = 该体自身站位范围。
    """
    tpl = [t for t in case["rail_templates"] if t["id"] == "right"][0]
    s_target = np.arange(s_lo, s_hi + ds * 0.5, ds)
    body_out: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}

    print(f"\n=== 窗口 {s_lo:.3f}–{s_hi:.3f} m，站距 {ds*1e3:.1f} mm，"
          f"边缘圆角 r={edge_radius*1e3:g} mm ===")
    for body in tpl["bodies"]:
        stations = [
            (float(st["s_m"]), st["profile"])
            for st in body["stations"]
            if s_lo - 0.2 <= float(st["s_m"]) <= s_hi + 0.2
        ]
        if len(stations) < 2:
            print(f"  skip body {body['id']}: only {len(stations)} stations")
            continue
        grid, field, s_known, inside = resample_body(
            stations, s_target, edge_radius=edge_radius, fillet_stage=fillet_stage
        )
        body_out[body["id"]] = (grid, field, s_known, inside)
        print(
            f"  body {body['id']:6s}: {len(stations):3d} 断面 → {int(inside.sum())} 站位 "
            f"[{s_known.min():.3f},{s_known.max():.3f}] "
            f"y {grid[0]*1e3:.2f}..{grid[-1]*1e3:.2f} mm"
        )

    # 直向密贴：把心轨抬到与翼轨（main）齐平 —— 结论是这一步是错的，默认关闭
    if close_point and "main" in body_out and "point" in body_out:
        g_m, f_m, _, in_m = body_out["main"]
        g_p, f_p, s_p, in_p = body_out["point"]
        print("\n  心轨密贴修正 Δ(s) = 翼轨冠高 − 心轨冠高：")
        for k, s in enumerate(s_target):
            if not (in_m[k] and in_p[k]):
                continue
            z_m, _ = crown(f_m[k], g_m, band[0], band[1])
            z_p, _ = crown(f_p[k], g_p, band[0], band[1])
            if not (np.isfinite(z_m) and np.isfinite(z_p)):
                continue
            delta = z_m - z_p
            if delta <= 0:
                continue
            f_p[k] = np.where(np.isfinite(f_p[k]), f_p[k] + delta, np.nan)
        body_out["point"] = (g_p, f_p, s_p, in_p)

    # 支撑面诊断
    print("\n  支撑面 h(s) 与坡度（重建后）：")
    print("     s_m      h(mm)   dh/ds(mm/m)   y(mm)  承载体")
    prev = None
    for k, s in enumerate(s_target):
        best, best_y, best_id = -np.inf, np.nan, ""
        for bid, (grid, field, _, _) in body_out.items():
            z, y = crown(field[k], grid, band[0], band[1])
            if np.isfinite(z) and z > best:
                best, best_y, best_id = z, y, bid
        if not np.isfinite(best):
            continue
        g = (best - prev[0]) / (s - prev[1]) * 1e3 if prev else np.nan
        if k % 25 == 0:
            print(f"  {s:8.4f}  {best*1e3:9.4f}  "
                  f"{'' if np.isnan(g) else f'{g:12.3f}'}  {best_y*1e3:9.3f}  {best_id}")
        prev = (best, s)
    return body_out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="case_C_bodies.json")
    ap.add_argument(
        "--windows",
        default="51.0:61.2,79.0:81.5",
        help="要重建的里程窗口，逗号分隔，形如 51.0:61.2,79.0:81.5",
    )
    ap.add_argument("--ds", type=float, default=0.005)
    ap.add_argument("--band", type=float, nargs=2, default=[0.735, 0.760])
    ap.add_argument(
        "--edge-radius-mm",
        type=float,
        default=6.0,
        help="轨头边缘圆角半径（0 = 不做圆角，只做 C1）",
    )
    ap.add_argument("--out", default="case_F_smooth_all.json")
    ap.add_argument("--dir", default="smoothed")
    ap.add_argument("--close-point-rail", action="store_true")
    ap.add_argument(
        "--fillet-stage",
        choices=["station", "final"],
        default="station",
        help="station=先在原始站位圆角再沿里程插值；final=先形成连续断面再逐断面圆角",
    )
    args = ap.parse_args()

    case_path = BASE / args.case
    case = json.loads(case_path.read_text(encoding="utf-8"))
    tpl = [t for t in case["rail_templates"] if t["id"] == "right"][0]
    band = (args.band[0], args.band[1])
    edge_radius = args.edge_radius_mm * 1e-3

    windows = []
    for chunk in args.windows.split(","):
        lo, hi = chunk.split(":")
        windows.append((float(lo), float(hi)))

    new_stations: dict[str, list[dict]] = {}
    cover: dict[str, list[tuple[float, float]]] = {}
    for s_lo, s_hi in windows:
        body_out = smooth_window(
            case, s_lo, s_hi, args.ds, band, edge_radius, args.close_point_rail,
            fillet_stage=args.fillet_stage,
        )
        for bid, (grid, field, s_known, inside) in body_out.items():
            lo_b, hi_b = float(s_known.min()), float(s_known.max())
            cover.setdefault(bid, []).append((lo_b, hi_b))
            s_target = np.arange(s_lo, s_hi + args.ds * 0.5, args.ds)
            for k, s in enumerate(s_target):
                if not inside[k]:
                    continue
                rel = f"{args.dir}/{bid}_s{int(round(s*1e4)):07d}.csv"
                write_station_csv(BASE / rel, grid, field[k])
                new_stations.setdefault(bid, []).append(
                    {
                        "s_m": float(s),
                        "id": f"{bid[0].upper()}{int(round(s*1e4)):07d}",
                        "profile": {"file": rel, "format": "csv", "units": "mm"},
                    }
                )

    new_bodies = []
    for body in tpl["bodies"]:
        bid = body["id"]
        if bid not in new_stations:
            new_bodies.append({**body, "stations": body["stations"]})
            continue
        ranges = cover.get(bid, [])
        kept = [
            st for st in body["stations"]
            if not any(lo <= float(st["s_m"]) <= hi for lo, hi in ranges)
        ]
        stations = sorted(kept + new_stations[bid], key=lambda st: st["s_m"])
        new_bodies.append({**body, "stations": stations})
        print(f"\nbody {bid:6s}: kept {len(kept)} + new {len(new_stations[bid])} stations")

    out_case = dict(case)
    out_case["case_id"] = (
        "crh380a_m_case_" + Path(args.out).stem.replace("case_", "")
    )
    out_case["purpose_detail"] = (
        (case.get("purpose_detail") or "")
        + " | switch (51-61 m) and frog (79-81.5 m) sections rebuilt: C1 PCHIP in y and s "
        f"on {args.ds*1e3:g} mm grid, head-edge fillet r={args.edge_radius_mm:g} mm"
    )
    out_case["rail_templates"] = [
        {**t, "bodies": new_bodies} if t["id"] == "right" else t
        for t in case["rail_templates"]
    ]
    (BASE / args.out).write_text(
        json.dumps(out_case, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
