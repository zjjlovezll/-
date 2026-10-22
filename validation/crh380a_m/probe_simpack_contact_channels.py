"""Dump every channel Simpack recorded for the wheel-rail contact pair.

The decisive question: at the frog, which lateral position did Simpack's contact
point sit at, and on which surface? If its output carries the contact point
coordinates we can compare body-for-body instead of guessing from the wheelset
displacement alone.

Usage: python probe_simpack_contact_channels.py <350.mat> [substring]
"""
from __future__ import annotations

import sys
from pathlib import Path

import h5py


def walk(node, path: str, out: list[tuple[str, tuple]], depth: int = 0) -> None:
    if isinstance(node, h5py.Dataset):
        out.append((path, node.shape))
        return
    for key in node:
        child = node[key]
        walk(child, f"{path}/{key}" if path else key, out, depth + 1)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    path = Path(argv[1])
    needle = argv[2] if len(argv) > 2 else "Contact"
    found: list[tuple[str, tuple]] = []
    with h5py.File(path, "r") as handle:
        walk(handle, "", found)
    hits = [(p, s) for p, s in found if needle.lower() in p.lower()]
    print(f"total datasets: {len(found)}; matching '{needle}': {len(hits)}")
    for p, s in hits:
        print(f"  {p}  shape={s}")
    groups = sorted({"/".join(p.split("/")[:-1]) for p, _ in found})
    print(f"\ntop-level groups ({len(groups)}):")
    seen: set[str] = set()
    for g in groups:
        head = "/".join(g.split("/")[:3])
        if head not in seen:
            seen.add(head)
            print(f"  {head}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
