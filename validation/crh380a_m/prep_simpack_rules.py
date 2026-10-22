"""Reproduce Simpack's documented rail-profile preprocessing on the raw ``.prr`` files.

Simpack 2021x states (``spckdoc`` pages *Profile Data and Preprocessing* and
*Lateral Sections*):

1. "a check is performed if the current slope is greater than 88.6 deg
   (= 40.9 : 1).  The according points are removed and a warning message is
   printed to the Message Log."
2. "In rail profiles, the profile is cut into different lateral sections if two
   adjacent profile points have the same y position or if their y positions are
   not monotonically increasing (i.e. if the profile is vertical or forms an
   undercut)."
3. Additionally, adjacent points further apart than ``split.dist`` split the
   profile; ``split.dist`` is absent from these files.

The solver log of the reference run reports, for every profile,

    129 point(s) with slope > 40.900000:1 had to be removed.

so the removal rule is testable: a faithful implementation must reproduce that
count for ``Profile_Mileage_JBG.prr``.

Usage::

    python prep_simpack_rules.py count <file.prr>
    python prep_simpack_rules.py sweep            # all referenced profiles
    python prep_simpack_rules.py station <station_m>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

SLOPE_LIMIT = 40.9
CATALOG = Path(r"F:\ai道岔状态反演辨识\Velch\diagnostics\crh380a_m_track_catalog.json")


def read_prr(path: Path) -> tuple[dict[str, str], np.ndarray]:
    """Return the spline header keywords and the (n, 2) profile points."""
    header: dict[str, str] = {}
    ys: list[float] = []
    zs: list[float] = []
    inside = False
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.split("!", 1)[0].strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("point.begin"):
            inside = True
            continue
        if low.startswith("point.end"):
            inside = False
            continue
        if inside:
            fields = line.replace(",", " ").split()
            if len(fields) >= 2:
                ys.append(float(fields[0]))
                zs.append(float(fields[1]))
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            header[key.strip()] = value.strip()
    return header, np.column_stack([np.asarray(ys), np.asarray(zs)])


def steep_mask(points: np.ndarray, limit: float = SLOPE_LIMIT) -> np.ndarray:
    """Flag points belonging to a segment steeper than ``limit`` (|dz/dy|)."""
    dy = np.diff(points[:, 0])
    dz = np.diff(points[:, 1])
    with np.errstate(divide="ignore", invalid="ignore"):
        slope = np.where(np.abs(dy) > 1e-12, np.abs(dz / dy), np.inf)
    steep = np.abs(slope) > limit
    mask = np.zeros(len(points), dtype=bool)
    mask[:-1] |= steep
    mask[1:] |= steep
    return mask


def sections_of(points: np.ndarray, split_dist: float | None = None) -> list[tuple[int, int]]:
    """Split into lateral sections following rule 2 (+ optional ``split.dist``)."""
    outs: list[tuple[int, int]] = []
    start = 0
    for index in range(len(points) - 1):
        y0, z0 = points[index]
        y1, z1 = points[index + 1]
        dy = y1 - y0
        far = split_dist is not None and np.hypot(dy, z1 - z0) > split_dist
        if dy <= 0 or far:
            outs.append((start, index + 1))
            start = index + 1
    outs.append((start, len(points)))
    return outs


def count(path: Path) -> None:
    header, points = read_prr(path)
    mask = steep_mask(points)
    print(f"{path.name}: {len(points)} points, steep-flagged {int(mask.sum())}")
    for key in ("approx.smooth", "point.dist.min", "split.dist", "shift.y", "shift.z", "rot.angle"):
        if key in header:
            print(f"  {key:16s} = {header[key]}")
    kept = points[~mask]
    print(f"  kept {len(kept)}; sections after removal: {len(sections_of(kept))}")


def station(which: float) -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    candidates = [
        ref for ref in catalog["profile_references"]
        if ref["side"] == "right" and abs(ref["station_m"] - which) < 1e-6
    ]
    for ref in candidates:
        path = Path(ref["path"])
        header, points = read_prr(path)
        mask = steep_mask(points)
        kept = points[~mask]
        print(f"\n=== s={ref['station_m']:.4f} m  {path.name}  index={ref['index']}")
        print(f"raw {len(points)} pts  steep-removed {int(mask.sum())}  kept {len(kept)}")
        print(f"raw y [{points[:,0].min():.3f}, {points[:,0].max():.3f}] mm  "
              f"z [{points[:,1].min():.3f}, {points[:,1].max():.3f}] mm")
        raw_sec = sections_of(kept)
        print(f"sections after removal: {len(raw_sec)} -> {raw_sec[:6]}")
        for lo, hi in raw_sec:
            part = kept[lo:hi]
            print(f"   section [{lo}:{hi}] n={hi-lo} y {part[:,0].min():.2f}..{part[:,0].max():.2f} "
                  f"z {part[:,1].min():.2f}..{part[:,1].max():.2f}")


def sweep() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    seen: dict[str, tuple[int, int]] = {}
    for ref in catalog["profile_references"]:
        path = Path(ref["path"])
        if path.name in seen:
            continue
        _, points = read_prr(path)
        mask = steep_mask(points)
        seen[path.name] = (len(points), int(mask.sum()))
    counts = sorted({removed for _, removed in seen.values()})
    print(f"{len(seen)} distinct profiles; removed-point counts: {counts}")
    for name, (total, removed) in sorted(seen.items()):
        if removed not in (counts[0], counts[-1]):
            print(f"  {name}: {total} pts, removed {removed}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["count", "sweep", "station"])
    ap.add_argument("arg", nargs="?")
    args = ap.parse_args(argv[1:])
    if args.action == "sweep":
        sweep()
        return 0
    if not args.arg:
        print("need a path or station")
        return 2
    if args.action == "count":
        count(Path(args.arg))
        return 0
    station(float(args.arg))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
