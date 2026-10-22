"""Acceptance metrics for a frog-passage run, read from history.csv.

The vendor's own run never loses contact: its minimum geometric penetration is
4.8 um and its minimum normal force 8.66 kN. Peak force alone therefore cannot
say whether a model is right; the two numbers that can are
``min penetration`` and ``min normal force`` while the wheel is on the frog.

Usage:
    python -X utf8 minpen_report.py <history.csv> [<history.csv> ...]
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

RAILS = ("axle1_left", "axle1_right", "axle2_left", "axle2_right")


def read_columns(path: Path) -> dict[str, list[float]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    data: dict[str, list[float]] = {name: [] for name in rows[0]}
    for row in rows:
        for name in data:
            data[name].append(float(row[name]))
    return data


def summarise(path: Path) -> dict[str, object]:
    data = read_columns(path)
    out: dict[str, object] = {"samples": len(data["time_s"]), "rails": {}}
    for rail in RAILS:
        pen = data[f"{rail}_penetration_m"]
        force = data[f"{rail}_normal_n"]
        active = data[f"{rail}_active"]
        loaded = [p for p, a in zip(pen, active) if a > 0.5]
        out["rails"][rail] = {
            "peak_kn": max(force) / 1e3,
            "min_kn": min(force) / 1e3,
            "mean_kn": sum(force) / len(force) / 1e3,
            "lost_samples": sum(1 for a in active if a < 0.5),
            "min_pen_um": (min(loaded) * 1e6) if loaded else 0.0,
            "max_pen_mm": max(pen) * 1e3,
        }
    z = data["axle1_z_m"]
    out["wheelset_z_span_mm"] = (max(z) - min(z)) * 1e3
    return out


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    header = f"{'case':38s} {'rail':12s} {'peak':>8s} {'min':>7s} {'mean':>7s} {'lost':>6s} {'minpen':>8s} {'maxpen':>7s}"
    print(header)
    print("-" * len(header))
    for target in argv[1:]:
        path = Path(target)
        summary = summarise(path)
        label = path.parent.name[:38]
        for rail in ("axle1_left", "axle1_right"):
            stats = summary["rails"][rail]
            print(f"{label:38s} {rail:12s} {stats['peak_kn']:8.1f} {stats['min_kn']:7.2f} "
                  f"{stats['mean_kn']:7.1f} {stats['lost_samples']:6d} "
                  f"{stats['min_pen_um']:8.1f} {stats['max_pen_mm']:7.3f}")
        print(f"{label:38s} {'wheelset z span':12s} {summary['wheelset_z_span_mm']:.3f} mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
