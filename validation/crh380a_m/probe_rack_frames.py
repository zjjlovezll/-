"""Second pass on the rack-turnout result file: enumerate the result frames and the time base."""

from __future__ import annotations

import json
from pathlib import Path

import h5py
import numpy as np

OUTPUT = Path(r"H:\齿轨工况\坡度工况\matlab\VEH_GEAR0_FX_STR_RACKN_QY-Re1_cjy_whcl_zn_TE_USERFORCE_CG_120.output")
PLAIN = OUTPUT / "NoExt_zgzn_jdz6.2mm_SP_00.mat"


def decode(node: h5py.Dataset | None) -> str:
    if node is None:
        return ""
    try:
        data = np.asarray(node[...]).ravel()
    except Exception:  # noqa: BLE001 - metadata is best effort
        return ""
    if data.dtype.kind in ("u", "i"):
        return "".join(chr(int(v)) for v in data if 30 <= int(v) < 0x3000)
    return ""


def main() -> int:
    with h5py.File(PLAIN, "r") as handle:
        base = handle["timeInt"]
        print("timeInt datasets:", [k for k in base.keys() if isinstance(base[k], h5py.Dataset)])
        print("timeInt groups  :", [k for k in base.keys() if isinstance(base[k], h5py.Group)])

        results = base["RS_result"]
        frames = [k for k in results.keys() if isinstance(results[k], h5py.Group)]
        print(f"\nRS_result frames ({len(frames)}):")
        for name in frames:
            group = results[name]
            label = decode(group.get("c_name")) or decode(group.get("name"))
            print(f"  {name:<14} {label:<28} children={len(list(group.keys()))}")

        # descend one frame to see the pair/patch layout
        first = results[frames[0]]
        print(f"\n--- inside {frames[0]} ---")

        def depth(node: h5py.Group, level: int, path: str) -> None:
            if level > 2:
                return
            for name in list(node.keys()):
                child = node[name]
                if isinstance(child, h5py.Group):
                    print(f"{'  ' * level}{path}/{name}")
                    depth(child, level + 1, "")
                elif name == "values":
                    print(f"{'  ' * level}values shape={child.shape} {child.dtype}")

        depth(first, 1, "")

        # time base: look for a dataset whose values look like a monotone seconds axis
        candidate = None
        for frame in frames:
            for name, obj in results[frame].items():
                if not isinstance(obj, h5py.Group):
                    continue
                for sub in ("time", "Time", "time_s"):
                    if sub in obj and isinstance(obj[sub], h5py.Dataset):
                        candidate = obj[sub]
                        print(f"\ntime candidate {frame}/{name}/{sub}")
                        break
                if candidate is not None:
                    break
            if candidate is not None:
                break
        if candidate is not None:
            axis = np.asarray(candidate[...], dtype=float).ravel()
            print(f"  n={axis.size} range {axis.min():.6g}..{axis.max():.6g}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
