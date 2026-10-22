"""把道岔辙叉段（79.0-81.2 m）的右轨支撑面标高归零，修复 599 kN 峰值。

问题（见 STRAIGHT_BODY_GEOMETRY.md「更正」一节）：
    79.13-80.00 m 之间，可接触区（y = 725-785 mm）内的轨顶最高点比名义轮面低
    0.22-0.60 mm，轮子彻底失去支撑（205/2401 次脱空），随后撞回时动态侵入量
    放大到 0.92 mm，接触力冲到 599 kN。

处理：
    逐站计算 y ∈ [0.725, 0.785] m 内的轨顶最大值 sup(s)，把整条断面沿 z 平移
    −sup(s)，使该段的"支撑面"恒为 0。轨体之间的相对形状（心轨/翼轨/轮缘槽）
    完全保留，只归一化绝对标高——绝对标高本身受轨下垫板与安装公差控制，是自
    由量，不属于型面设计。

约定：
    右轨断面 spec 为 y_sign=+1, y_offset_m=+0.753, z_sign=-1，
    故 z_abs = -z_raw；把 z_abs 抬高 −sup 等价于 z_raw += sup。

用法：
    python validation/turnout18_ref/patch_frog_level.py
输出：
    validation/turnout18_ref/frogfix/R0xx.prr       补丁后的断面
    validation/turnout18_ref/frogfix/level_report.json
    validation/crh380a_m/case_B_turnout_frogfix.json
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from velch.profiles import load_profile

HERE = Path(__file__).resolve().parent
VELCH = HERE.parents[1]
CASE_IN = VELCH / "validation" / "crh380a_m" / "case_B_turnout.json"
CASE_OUT = VELCH / "validation" / "crh380a_m" / "case_B_turnout_frogfix.json"
OUT_DIR = HERE / "frogfix"

S_LO, S_HI = 79.0, 81.2          # 补丁区段
BAND_Y = (0.725, 0.785)          # 可接触带（由 WHEEL 前缘 + LMA 踏面确定）
TOL = 1e-6                       # 小于 1 µm 的 sup 视为无需平移


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def patch_prr(src: Path, dst: Path, dz_raw: float) -> None:
    """把 PRR 点块第二列（z_raw）整体加上 dz_raw。"""
    text = src.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    out: list[str] = []
    inside = False
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("point.begin"):
            inside = True
            out.append(line)
            out.append(f"! velch frog-level correction: dz_raw = {dz_raw:+.9e} m  (支撑面归零)")
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


def main() -> int:
    case = json.loads(CASE_IN.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report: list[dict] = []
    patched = 0

    for template in case["rail_templates"]:
        if template["id"] != "right":
            continue
        for station in template["stations"]:
            s = float(station["s_m"])
            if not (S_LO <= s <= S_HI):
                continue
            spec = dict(station["profile"])
            src = Path(spec["file"])
            prof = load_profile(
                src,
                file_format=spec["format"],
                surface="rail_top",
                y_scale_m=1.0,
                z_scale_m=1.0,
                y_sign=int(spec.get("y_sign", 1)),
                z_sign=int(spec.get("z_sign", 1)),
                y_offset_m=float(spec.get("y_offset_m", 0.0)),
                z_offset_m=float(spec.get("z_offset_m", 0.0)),
            )
            y = np.asarray(prof.y_m, float)
            z = np.asarray(prof.z_m, float)
            mask = (y >= BAND_Y[0]) & (y <= BAND_Y[1])
            if not mask.any():
                report.append({"s_m": s, "station": station["id"], "patched": False,
                               "reason": "band not covered by profile"})
                continue
            sup = float(z[mask].max())
            d_abs = -sup if sup < -TOL else 0.0
            dz_raw = -d_abs          # z_abs = -z_raw  =>  抬高 z_abs 等价于减小 z_raw
            entry = {
                "s_m": s,
                "station": station["id"],
                "src": str(src),
                "src_sha256": sha256(src),
                "support_max_before_mm": sup * 1e3,
                "shift_abs_mm": d_abs * 1e3,
                "patched": bool(abs(d_abs) > TOL),
            }
            if entry["patched"]:
                dst = OUT_DIR / f"{station['id']}.prr"
                patch_prr(src, dst, dz_raw)
                spec["file"] = str(dst)
                station["profile"] = spec
                entry["dst"] = str(dst)
                entry["dst_sha256"] = sha256(dst)
                patched += 1
            report.append(entry)

    case["case_id"] = "crh380a_m_turnout18_frogfix"
    case["purpose_detail"] = (
        "CRH380A_M on the 18号 turnout, with the frog section (79.0-81.2 m) right-rail "
        "support level normalised to z=0 so that the reachable rail-top surface is "
        "continuous. Everything else is identical to case_B_turnout."
    )
    CASE_OUT.write_text(json.dumps(case, ensure_ascii=False, indent=1), encoding="utf-8")

    (OUT_DIR / "level_report.json").write_text(
        json.dumps({"s_lo": S_LO, "s_hi": S_HI, "band_y_m": BAND_Y,
                    "patched_count": patched, "stations": report},
                   ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"patched {patched} station profile(s) in [{S_LO}, {S_HI}] m")
    print(f"case  -> {CASE_OUT}")
    print(f"report-> {OUT_DIR / 'level_report.json'}")
    print()
    print("   s(m)   sup(s) mm   shift mm")
    for e in report:
        if "support_max_before_mm" in e:
            flag = "  *" if e["patched"] else ""
            print(f"  {e['s_m']:7.3f}  {e['support_max_before_mm']:10.3f}  {e['shift_abs_mm']:9.3f}{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
