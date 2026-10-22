"""Probe the rack-turnout Simpack result files (HDF5 .mat) and report their structure.

Two exported variants exist: ``NoExt_zgzn_jdz6.2mm_SP_00.mat`` (398 MB) and
``..._3d.mat`` (596 MB).  Both are read-only here; the goal is to learn the channel layout,
the time base, and what the ``_3d`` variant adds.
"""

from __future__ import annotations

import json
from pathlib import Path

import h5py
import numpy as np

OUTPUT = Path(r"H:\齿轨工况\坡度工况\matlab\VEH_GEAR0_FX_STR_RACKN_QY-Re1_cjy_whcl_zn_TE_USERFORCE_CG_120.output")
FILES = {"plain": OUTPUT / "NoExt_zgzn_jdz6.2mm_SP_00.mat",
         "three_d": OUTPUT / "NoExt_zgzn_jdz6.2mm_SP_00_3d.mat"}


def walk(node: h5py.Group, depth: int, prefix: str, rows: list[str], limit: int = 40) -> None:
    if len(rows) >= limit:
        return
    keys = list(node.keys())
    datasets = [k for k in keys if isinstance(node[k], h5py.Dataset)]
    groups = [k for k in keys if isinstance(node[k], h5py.Group)]
    rows.append(f"{'  ' * depth}{prefix or '/'}  ({len(datasets)} datasets, {len(groups)} groups)")
    for name in datasets[:6]:
        dataset = node[name]
        rows.append(f"{'  ' * (depth + 1)}{name}  shape={dataset.shape} {dataset.dtype}")
    for name in groups[:8]:
        walk(node[name], depth + 1, name, rows, limit)


def main() -> int:
    report: dict[str, object] = {}
    for label, path in FILES.items():
        if not path.exists():
            print(f"MISSING {path}")
            continue
        with h5py.File(path, "r") as handle:
            total = {"datasets": 0, "groups": 0}

            def counter(_name, _obj) -> None:
                if isinstance(_obj, h5py.Dataset):
                    total["datasets"] += 1
                else:
                    total["groups"] += 1

            handle.visititems(counter)
            rows: list[str] = []
            walk(handle, 0, "", rows)
            print(f"\n===== {label}: {path.name} ({path.stat().st_size / 1e6:.1f} MB) =====")
            print(f"objects: {total['datasets']} datasets, {total['groups']} groups")
            print("\n".join(rows[:28]))

            # time base: find a dataset named 'time' or the first 1-D values under timeInt
            time_info = None
            found: list[str] = []

            def find_time(name: str, obj: h5py.Dataset) -> None:
                if len(found) > 6:
                    return
                if isinstance(obj, h5py.Dataset) and obj.size and obj.ndim >= 1:
                    lname = name.lower()
                    if "time" in lname and obj.size < 1e7:
                        found.append(name)

            handle.visititems(find_time)
            for name in found[:4]:
                data = np.asarray(handle[name][...], dtype=float).ravel()
                if data.size > 1:
                    print(f"time-like {name}: n={data.size} "
                          f"range {data.min():.6g}..{data.max():.6g}")
                    time_info = (name, int(data.size), float(data.min()), float(data.max()))
                    break

            report[label] = {"path": str(path), "datasets": total["datasets"],
                             "groups": total["groups"], "time": time_info,
                             "top": list(handle.keys())[:20]}
    Path("rack_result_structure.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
