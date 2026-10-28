"""Extract the designed lowering of the switch rail and the frog nose from the 18-turnout sections.

The user's validation idea is to invert something whose truth is *design*, not something we wrote
into the case: the lowering value of the switch rail (尖轨降低值) and of the frog nose (心轨降低值).
Both are geometric facts of the turnout, so a zero-irregularity run that recovers them validates the
whole geometric transfer chain, not just the estimator.

The sections live in the SDITT turnout set (``WRProfile-07(009)-1_18``): five families, each with a
mileage table

    07(009)-Mileage-zjg_zgyg.txt     straight switch rail / straight wing rail, from 50.575 m
    07(009)-Mileage-qjbg.txt         curved stock rail, from 50.000 m
    07(009)-Mileage-qjg_cgyg.txt     curved switch rail, from 50.578 m
    07(009)-Mileage-cxg.txt          frog (心轨), from 103.280 m

and each profile a two-column (y, z) text file in metres.

This script does not model anything: it reads those sections and reports, per mileage, the crown
height of each family against the plain rail (``jbg-20200418-R``), i.e. the designed lowering. It
also reports the crown's lateral position, because a section that is *narrower* (a blade) rather than
lower can fool a height-only reading.

Run:

    python -X utf8 scripts/s49_design_lowering.py            # summary tables
    python -X utf8 scripts/s49_design_lowering.py --every 2  # one row every 2 m
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

DESIGN_ROOT = Path(r"G:/研究生/SDITT-RW-FT-250728/SDITT-RW-FT-250728/WRProfile-07(009)-1_18")
MILEAGE_DIR = DESIGN_ROOT / "07(009)-Mileage"
PLAIN = "jbg-20200418-R.txt"

FAMILIES = {
    "straight_switch": "07(009)-Mileage-zjg_zgyg.txt",
    "curved_stock": "07(009)-Mileage-qjbg.txt",
    "curved_switch": "07(009)-Mileage-qjg_cgyg.txt",
    "frog": "07(009)-Mileage-cxg.txt",
}


def find(name: str) -> Path:
    for directory in DESIGN_ROOT.iterdir():
        candidate = directory / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"{name} not found under {DESIGN_ROOT}")


def load_section(name: str) -> tuple[np.ndarray, np.ndarray]:
    """Two columns, metres: lateral offset and height, sorted by offset."""

    path = find(name)
    rows = [line.split() for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()]
    values = np.array([[float(row[0]), float(row[1])] for row in rows], dtype=float)
    order = np.argsort(values[:, 0])
    return values[order, 0], values[order, 1]


def crown(name: str) -> tuple[float, float]:
    """Height of the highest point of a section, and where that point sits laterally."""

    y, z = load_section(name)
    index = int(np.argmax(z))
    return float(z[index]), float(y[index])


def table(name: str) -> list[tuple[float, str]]:
    path = MILEAGE_DIR / name
    rows = [line.split() for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip()]
    return [(float(row[0]), row[1]) for row in rows]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--every", type=float, default=5.0, help="print step along the route, m")
    args = parser.parse_args(argv)

    plain_height, plain_y = crown(PLAIN)
    print(f"plain rail {PLAIN}: crown z {plain_height * 1e3:+.3f} mm at y {plain_y * 1e3:+.3f} mm")

    for family, table_name in FAMILIES.items():
        stations = table(table_name)
        mileages = np.array([s for s, _ in stations])
        names = [n for _, n in stations]
        print(f"\n{family:16s} {table_name}  {len(stations)} stations "
              f"{mileages.min():.3f}..{mileages.max():.3f} m  "
              f"step {np.median(np.diff(np.unique(mileages))) * 1e3:.1f} mm")
        # Unique mileages only: the pair tables repeat a station for the two rails that share it.
        seen: set[float] = set()
        printed = 0.0
        rows: list[tuple[float, float, float]] = []
        for mileage, section in stations:
            if mileage in seen:
                continue
            seen.add(mileage)
            height, crown_y = crown(section)
            rows.append((mileage, (height - plain_height) * 1e3, (crown_y - plain_y) * 1e3))
        values = np.array(rows)
        print(f"    lowering vs plain rail: min {values[:, 1].min():+8.3f} mm  "
              f"max {values[:, 1].max():+8.3f} mm   crown y shift "
              f"{values[:, 2].min():+7.3f}..{values[:, 2].max():+7.3f} mm")
        print("    mileage      Δcrown(mm)   Δy(mm)   section")
        for mileage, section in stations:
            if mileage < printed:
                continue
            printed = mileage + args.every
            height, crown_y = crown(section)
            print(f"    {mileage:8.3f}  {(height - plain_height) * 1e3:+10.3f}  "
                  f"{(crown_y - plain_y) * 1e3:+7.3f}   {section}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
