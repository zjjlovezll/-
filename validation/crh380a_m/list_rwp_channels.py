"""Decode Simpack's RWP contact result containers.

The reference run writes, per rail-wheel pair and per contact patch,
``/RS_result/SRS_S_F/SRS_S_WS_F/SRS_RWP_<side>[_<patch>]/ch_NNN`` groups holding
``name``, ``unit``, ``description`` and a ``values`` array.  Reading them gives
Simpack's own contact-point position and penetration, which is what the Velch
comparison needs.

Usage::

    python list_rwp_channels.py <350.mat>                 # channel catalogue
    python list_rwp_channels.py <350.mat> --catalog       # same, with descriptions
    python list_rwp_channels.py <350.mat> --series        # value ranges per channel
"""
from __future__ import annotations

import sys
from pathlib import Path

import h5py
import numpy as np


def scalar(node: h5py.Group, key: str) -> str:
    if key not in node:
        return ""
    value = node[key][()]
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    if isinstance(value, np.ndarray):
        return str(value.ravel()[0]) if value.size else ""
    return str(value)


def patch_groups(handle: h5py.File) -> list[str]:
    out: list[str] = []
    root = handle.get("RS_result")
    if root is None and "timeInt" in handle:
        root = handle["timeInt"].get("RS_result")
    if root is None:
        return out

    def walk(node, prefix: str = "") -> None:
        if isinstance(node, h5py.Group):
            keys = list(node.keys())
            if any(key.startswith("ch_") for key in keys):
                out.append(prefix)
                return
            for key in keys:
                walk(node[key], f"{prefix}/{key}" if prefix else key)

    walk(root)
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = Path(argv[1])
    want_catalog = "--catalog" in argv
    want_series = "--series" in argv
    with h5py.File(path, "r") as handle:
        groups = patch_groups(handle)
        print(f"{len(groups)} contact patch container(s)")
        root = handle.get("RS_result")
        if root is None:
            root = handle["timeInt"]["RS_result"]
        for group_path in groups:
            group = root[group_path]
            channels = sorted(key for key in group.keys() if key.startswith("ch_"))
            print(f"\n=== {group_path}  ({len(channels)} channels)")
            for channel in channels:
                node = group[channel]
                name = scalar(node, "c_name") or scalar(node, "name")
                unit = scalar(node, "unit")
                description = scalar(node, "description")
                values = node["values"][()] if "values" in node else None
                shape = getattr(values, "shape", None)
                if want_series and values is not None:
                    flat = np.asarray(values, dtype=float).ravel()
                    finite = flat[np.isfinite(flat)]
                    span = (
                        f"[{finite.min():+.6g}, {finite.max():+.6g}]"
                        if finite.size
                        else "[no finite values]"
                    )
                else:
                    span = ""
                line = f"  {channel} {name:<34s} {unit:<10s} shape={shape} {span}"
                if want_catalog:
                    line += f"\n      {description[:160]}"
                print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
