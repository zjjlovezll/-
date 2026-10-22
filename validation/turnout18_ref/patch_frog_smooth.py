"""把辙叉段（78.5-81.5 m）右轨支撑面的"里程斜率"限制到维护极限以内。

背景（见 FROG_IMPACT_MECHANISM.md）：
    原始 236 个里程断面里，整条 150 m 只有 7 个区间的支撑面斜率超过 1 mm/m，
    而这 7 个全部落在 80.004-80.278 m —— 心轨尖端与翼轨融合处。那里相邻站距
    只有 30.4 mm，支撑面却一步抬 0.135 mm，等效坡度 +4.5 mm/m（350 km/h 下
    轨面垂直速度 0.44 m/s）。Velch 在这种台阶上会"弹射"轮对：z 从 -0.48 mm
    弹到 +1.93 mm，腾空 2 m，再以 0.9 mm 侵入落地 → 600 kN 假峰值。

处理：
    对右轨 78.5-81.5 m 的每个站位，取其可接触带 [0.725, 0.785] m 内的轨顶最大
    值 sup(s)，把 sup(s) 投影到"斜率受限"集合 |d sup/d s| <= L 上（前后两遍
    截断，等价于 L∞ 投影），得到目标标高 t(s)，再把整条断面平移 t(s) - sup(s)。

    只改绝对标高、不改断面内部形状；平移量本身是光滑的，所以不会引入新台阶。
    L 默认 0.2 mm/m —— 这是本线其余 219 个站间区间的 p90。

用法：
    python validation/turnout18_ref/patch_frog_smooth.py [--slope-limit-mm-per-m 0.2]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from velch.profiles import load_profile

HERE = Path(__file__).resolve().parent
VELCH = HERE.parents[1]
CASE_IN = VELCH / "validation" / "crh380a_m" / "case_B_turnout.json"
OUT_DIR = HERE / "frogsmooth"

S_LO, S_HI = 78.5, 81.5
BAND_Y = (0.725, 0.785)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_support(spec: dict) -> tuple[np.ndarray, np.ndarray]:
    prof = load_profile(
        Path(spec["file"]),
        file_format=spec["format"],
        surface="rail_top",
        y_scale_m=1.0,
        z_scale_m=1.0,
        y_sign=int(spec.get("y_sign", 1)),
        z_sign=int(spec.get("z_sign", 1)),
        y_offset_m=float(spec.get("y_offset_m", 0.0)),
        z_offset_m=float(spec.get("z_offset_m", 0.0)),
    )
    return np.asarray(prof.y_m, float), np.asarray(prof.z_m, float)


def slope_limit_project(s: np.ndarray, v: np.ndarray, limit: float) -> np.ndarray:
    """把序列 v 投影到 |Δv| <= limit·Δs 的集合上（前后两遍截断）。"""
    out = v.astype(float).copy()
    for i in range(1, len(out)):
        cap = out[i - 1] + limit * (s[i] - s[i - 1])
        if out[i] > cap:
            out[i] = cap
    for i in range(len(out) - 2, -1, -1):
        cap = out[i + 1] + limit * (s[i + 1] - s[i])
        if out[i] > cap:
            out[i] = cap
    return out


def patch_prr(src: Path, dst: Path, dz_raw: float, note: str) -> None:
    text = src.read_text(encoding="utf-8", errors="replace")
    out: list[str] = []
    inside = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("point.begin"):
            inside = True
            out.append(line)
            out.append(f"! velch frog-smooth: dz_raw = {dz_raw:+.9e} m  ({note})")
            continue
        if stripped.lower().startswith("point.end"):
            inside = False
            out.append(line)
            continue
        if inside and stripped and not stripped.startswith("!"):
            f = stripped.split()
            if len(f) >= 2:
                z = float(f[1]) + dz_raw
                tail = " ".join(f[2:])
                out.append(f"  {float(f[0]):+.12e}  {z:+.12e}" + (f"  {tail}" if tail else ""))
                continue
        out.append(line)
    dst.write_text("\n".join(out) + "\n", encoding="utf-8")


def _abs_profile(spec: dict, surface: str) -> tuple[np.ndarray, np.ndarray]:
    prof = load_profile(
        Path(spec["file"]),
        file_format=spec["format"],
        surface=surface,
        y_scale_m=1.0,
        z_scale_m=1.0,
        y_sign=int(spec.get("y_sign", 1)),
        z_sign=int(spec.get("z_sign", 1)),
        y_offset_m=float(spec.get("y_offset_m", 0.0)),
        z_offset_m=float(spec.get("z_offset_m", 0.0)),
    )
    return np.asarray(prof.y_m, float), np.asarray(prof.z_m, float)


def corridor_height(
    spec: dict,
    wheel_y: np.ndarray,
    wheel_z: np.ndarray,
    wheel_offset_m: float,
    wheel_centre_z_m: float,
) -> tuple[float, float] | None:
    """轮子实际走的那一点：返回 (接触点横位, 该点轨面绝对标高)。

    与求解器相同口径：在轮/轨横位重叠区上取"侵入最深"的位置。
    """
    rail_y, rail_z = _abs_profile(spec, "rail_top")
    wy = wheel_y + wheel_offset_m
    lower = max(float(wy[0]), float(rail_y[0]))
    upper = min(float(wy[-1]), float(rail_y[-1]))
    if upper <= lower:
        return None
    grid = np.union1d(
        np.union1d(rail_y, wy),
        np.union1d(wy[(wy > lower) & (wy < upper)], rail_y[(rail_y > lower) & (rail_y < upper)]),
    )
    grid = grid[(grid >= lower) & (grid <= upper)]
    if grid.size < 3:
        return None
    wz = np.interp(grid, wy, wheel_z) + wheel_centre_z_m
    rz = np.interp(grid, rail_y, rail_z)
    depth = rz - wz
    k = int(np.argmax(depth))
    return float(grid[k]), float(rz[k])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slope-limit-mm-per-m", type=float, default=0.2)
    ap.add_argument("--metric", choices=["band_max", "corridor"], default="band_max",
                    help="band_max: 带内轨顶最高点；corridor: 静态轮位接触点处的轨面标高（轮子实际走的走廊）")
    ap.add_argument("--case", default=str(CASE_IN))
    ap.add_argument("--out", default=str(VELCH / "validation" / "crh380a_m" / "case_B_turnout_frogsmooth.json"))
    args = ap.parse_args()
    limit = args.slope_limit_mm_per_m * 1e-3

    case = json.loads(Path(args.case).read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    wheel_r = [w for w in case["wheels"] if w["id"] == "R"][0]
    wheel_z_m = 0.430 - 0.4628e-3

    # 只处理 zone 内的站位；先把它们按里程排好
    zone: list[tuple[float, dict, dict]] = []
    for template in case["rail_templates"]:
        if template["id"] != "right":
            continue
        for station in template["stations"]:
            s = float(station["s_m"])
            if S_LO <= s <= S_HI:
                zone.append((s, station, template))
    zone.sort(key=lambda item: item[0])
    if not zone:
        print("no station in zone")
        return 2

    s_arr = np.array([z[0] for z in zone])
    sup = np.empty_like(s_arr)
    corridor: list[tuple[float, float] | None] = []
    if args.metric == "corridor":
        wspec = wheel_r["profile"]
        wy, wz = _abs_profile(wspec, "wheel_lower")
    for i, (_s, station, _t) in enumerate(zone):
        if args.metric == "corridor":
            res = corridor_height(station["profile"], wy, wz, float(wheel_r["lateral_offset_m"]), wheel_z_m)
            corridor.append(res)
            if res is not None:
                sup[i] = res[1]
                continue
        y, z = load_support(station["profile"])
        m = (y >= BAND_Y[0]) & (y <= BAND_Y[1])
        if not m.any():
            print(f"station {station['id']} does not cover the band")
            return 3
        sup[i] = z[m].max()

    target = slope_limit_project(s_arr, sup, limit)
    shift = target - sup

    report = []
    for i, (s, station, _t) in enumerate(zone):
        spec = dict(station["profile"])
        src = Path(spec["file"])
        entry = {
            "s_m": s,
            "station": station["id"],
            "support_before_mm": sup[i] * 1e3,
            "support_after_mm": target[i] * 1e3,
            "shift_mm": shift[i] * 1e3,
            "src": str(src),
            "src_sha256": sha256(src),
        }
        if abs(shift[i]) > 1e-9:
            dst = OUT_DIR / f"{station['id']}.prr"
            patch_prr(src, dst, -shift[i], f"frog-smooth, target slope <= {args.slope_limit_mm_per_m} mm/m")
            spec["file"] = str(dst)
            station["profile"] = spec
            entry["dst"] = str(dst)
            entry["dst_sha256"] = sha256(dst)
        report.append(entry)

    out_path = Path(args.out)
    case["case_id"] = "crh380a_m_turnout18_frogsmooth"
    case["purpose_detail"] = (
        "CRH380A_M on the 18号 turnout. Right-rail support level in 78.5-81.5 m is projected "
        f"onto |d sup/d s| <= {args.slope_limit_mm_per_m} mm/m so that no station-to-station "
        "level step exceeds the maintenance limit. Cross-section shape is untouched."
    )
    out_path.write_text(json.dumps(case, ensure_ascii=False, indent=1), encoding="utf-8")

    ds_all = np.diff(s_arr)
    ok = ds_all > 1e-6
    slope_before = np.abs(np.diff(sup)[ok] / ds_all[ok]).max() * 1e3 if ok.any() else 0.0
    dsup = np.diff(target) / np.where(ds_all > 0, ds_all, 1.0) * 1e3
    slope_after = np.abs(dsup[ok]).max() if ok.any() else 0.0
    (OUT_DIR / "smooth_report.json").write_text(
        json.dumps({
            "s_lo": S_LO, "s_hi": S_HI, "band_y_m": BAND_Y,
            "metric": args.metric,
            "slope_limit_mm_per_m": args.slope_limit_mm_per_m,
            "max_shift_mm": float(np.abs(shift).max() * 1e3),
            "max_support_slope_before_mm_per_m": float(slope_before),
            "max_support_slope_after_mm_per_m": float(slope_after),
            "corridor": [None if c is None else {"y_m": c[0], "rail_z_m": c[1]} for c in corridor],
            "stations": report,
        }, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )

    print(f"zone stations: {len(zone)}  ({S_LO}-{S_HI} m)  metric={args.metric}")
    print("max |d h/d s| before: %.2f mm/m" % slope_before)
    print("max |d h/d s| after : %.2f mm/m" % slope_after)
    print("max shift: %.3f mm" % (np.abs(shift).max() * 1e3))
    print("case ->", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
