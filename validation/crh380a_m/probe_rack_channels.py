"""Third pass: time base, vehicle kinematics, and the contact channels of the rack result."""

from __future__ import annotations

import json
from pathlib import Path

import h5py
import numpy as np

OUTPUT = Path(r"H:\齿轨工况\坡度工况\matlab\VEH_GEAR0_FX_STR_RACKN_QY-Re1_cjy_whcl_zn_TE_USERFORCE_CG_120.output")
PLAIN = OUTPUT / "NoExt_zgzn_jdz6.2mm_SP_00.mat"


def values(node: h5py.Group, name: str) -> np.ndarray | None:
    if name not in node:
        return None
    child = node[name]
    if isinstance(child, h5py.Dataset):
        return np.asarray(child[...], dtype=float).ravel()
    if "values" in child:
        return np.asarray(child["values"][...], dtype=float).ravel()
    return None


def main() -> int:
    report: dict[str, object] = {}
    with h5py.File(PLAIN, "r") as handle:
        time_group = handle["timeInt/time"]
        axis = None
        if isinstance(time_group, h5py.Dataset):
            axis = np.asarray(time_group[...], dtype=float).ravel()
        elif "values" in time_group:
            axis = np.asarray(time_group["values"][...], dtype=float).ravel()
        if axis is not None:
            step = float(np.median(np.diff(axis)))
            print(f"time: n={axis.size} {axis.min():.6f}..{axis.max():.6f} s, dt={step:.6g} s")
            report["time"] = {"n": int(axis.size), "t0": float(axis.min()),
                              "t1": float(axis.max()), "dt": step}

        trans = handle["timeInt/bodyPosTrans"]
        bodies = sorted(trans.keys())
        print(f"\nbodyPosTrans bodies ({len(bodies)}): {bodies[:12]}")
        for body in bodies:
            group = trans[body]
            x = values(group, "x")
            if x is None:
                continue
            span = float(x.max() - x.min())
            if span > 1.0:
                duration = (axis.max() - axis.min()) if axis is not None else float("nan")
                speed = span / duration if duration else float("nan")
                print(f"  {body:<28} x {x.min():10.3f}..{x.max():10.3f} m  "
                      f"travelled {span:8.3f} m  mean {speed:6.2f} m/s ({speed * 3.6:5.1f} km/h)")
                report.setdefault("bodies", {})[body] = {
                    "x_min": float(x.min()), "x_max": float(x.max()), "span": span,
                    "mean_speed_m_s": speed}

        rwp = handle["timeInt/RS_result/SRS_S_B_F/SRS_S_WS_F/SRS_RWP_R"]
        patches = [k for k in rwp.keys() if k.startswith("SRS_RWP_R_")]
        print(f"\nfront-bogie front-wheelset RWP_R entries ({len(patches)}): {sorted(patches)[:8]}")
        pair = rwp.get("SRS_RWP_R_Pair")
        if pair is not None:
            channels = sorted(k for k in pair.keys() if k.startswith("ch_"))
            print(f"  pair channels: {len(channels)}")
            for wanted in ("ch_001", "ch_008", "ch_010", "ch_022"):
                if wanted in pair:
                    data = values(pair, wanted)
                    if data is not None:
                        print(f"    {wanted}: n={data.size} "
                              f"{data.min():.6g}..{data.max():.6g}")
        patch1 = rwp.get("SRS_RWP_R_1")
        if patch1 is not None:
            channels = sorted(k for k in patch1.keys() if k.startswith("ch_"))
            print(f"  patch[1] channels: {len(channels)}")
            for wanted in ("ch_003", "ch_010", "ch_025"):
                if wanted in patch1:
                    data = values(patch1, wanted)
                    if data is not None:
                        print(f"    {wanted}: n={data.size} "
                              f"{data.min():.6g}..{data.max():.6g}")

    Path("rack_result_channels.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
