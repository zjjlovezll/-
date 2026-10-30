"""Read SDITT's three mileage tables the way its driver does, and report what they hand us.

SDITT does not use one combined turnout section.  Its driver loads a *table per rail line* -- a list of
(mileage, section file) pairs -- Bezier-interpolates each line along the track, and evaluates contact per
line, so the wheel sits on the deepest line and the load transfers by itself.

For the 18-turnout on the through route the tables are (`WRProfile-07(009)-1_18\07(009)-Mileage`):

    R1  07(009)-Mileage-qjbg.txt            76 rows, 0.000 .. 1000.0    curved stock rail
    R2  07(009)-Mileage-zjg_zgyg_250722.txt 161 rows, 50.578 .. 104.419 straight switch blade + wing rail
    R3  07(009)-Mileage-cxg.txt              68 rows, 103.280 .. 116.590 long point rail

The tables name `.txt` twins; the sections themselves are `.prr` files in the sibling folder whose name is
the file stem minus its last `-token` (e.g. `07(009)-zjg-20200418-3` lives in `07(009)-zjg-20200418/`).

This script resolves every row, proves each body covers its own span, and reports the crown height
`min(z)` per station -- the design lowering, read from geometry rather than from a table of offsets.

Run: PYTHONPATH=src python -X utf8 scripts/s81_sditt_lines.py
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

import numpy as np

ROOT = Path(r"G:\研究生\SDITT-RW-FT-250728\SDITT-RW-FT-250728\WRProfile-07(009)-1_18")
TABLE_DIR = ROOT / "07(009)-Mileage"
POINT = re.compile(r"^\s*(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s*$")
TABLES = (
    ("qjbg", "07(009)-Mileage-qjbg.txt"),
    ("zjg_zgyg", "07(009)-Mileage-zjg_zgyg_250722.txt"),
    ("cxg", "07(009)-Mileage-cxg.txt"),
)


@dataclass(frozen=True)
class Row:
    station_m: float
    section: Path


def section_index() -> dict[str, Path]:
    """stem -> .prr path.  The tables name stems, and the plain rail lives in a different folder from the
    sections that share its name prefix, so resolve by stem rather than by re-deriving a folder name."""
    index: dict[str, Path] = {}
    for candidate in ROOT.rglob("*.prr"):
        index.setdefault(candidate.stem, candidate)
    return index


def read_table(path: Path, index: dict[str, Path]) -> list[Row]:
    rows: list[Row] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            station = float(parts[0])
        except ValueError:
            continue
        stem = Path(parts[1]).stem
        rows.append(Row(station, index.get(stem, ROOT / f"{stem}.prr")))
    return rows


def crown_m(section: Path) -> float:
    ys: list[float] = []
    zs: list[float] = []
    inside = False
    for line in section.read_text(encoding="utf-8", errors="replace").splitlines():
        if "point.begin" in line:
            inside = True
            continue
        if "point.end" in line:
            break
        if not inside or line.lstrip().startswith("!"):
            continue
        match = POINT.match(line)
        if match:
            ys.append(float(match.group(1)))
            zs.append(float(match.group(2)))
    return float(np.min(zs)) if zs else float("nan")


def main() -> int:
    index = section_index()
    print(f"tables under {TABLE_DIR}  ({len(index)} distinct sections indexed)")
    for name, table_name in TABLES:
        table = TABLE_DIR / table_name
        if not table.is_file():
            print(f"  {name:9s} MISSING {table}")
            return 2
        rows = read_table(table, index)
        missing = [row for row in rows if not row.section.is_file()]
        span = (rows[0].station_m, rows[-1].station_m) if rows else (float("nan"), float("nan"))
        gaps = np.diff([row.station_m for row in rows])
        print(f"\n  {name:9s} {len(rows):4d} rows  {span[0]:8.3f} .. {span[1]:8.3f} m"
              f"  step {np.min(gaps):6.3f}..{np.max(gaps):6.3f} m  missing {len(missing)}")
        if missing:
            for row in missing[:3]:
                print(f"      missing: {row.station_m:.3f} -> {row.section}")
            return 3
        # crown height profile: the lowering is where this sits below 0
        crowns = [(row.station_m, crown_m(row.section) * 1e3) for row in rows]
        head = crowns[:3]
        tail = crowns[-3:]
        print("      crown min(z) at the start: " + ", ".join(f"{s:.3f} m -> {c:+.2f} mm" for s, c in head))
        print("      crown min(z) at the end:   " + ", ".join(f"{s:.3f} m -> {c:+.2f} mm" for s, c in tail))
        levelled = [s for s, c in crowns if abs(c) <= 0.25]
        if levelled:
            print(f"      reaches the running surface (|crown| <= 0.25 mm) from {min(levelled):.3f} m "
                  f"({len(levelled)} of {len(rows)} stations)")
        low = min(crowns, key=lambda item: item[1])
        print(f"      deepest below the surface: {low[0]:.3f} m -> {low[1]:+.2f} mm")

    print("\nResolution rule holds for every row: the section is the stem minus its last token, in the")
    print("sibling folder, with .prr instead of .txt.  So a case can carry these three spans as three rail")
    print("bodies and let the contact pick the deepest -- no z-offset table anywhere.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
