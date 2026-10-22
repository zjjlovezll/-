"""Print raw PRR sections near the frog as (y, z) millimetres, split by polyline.

PRR files are structured text: ``point.begin`` / ``point.end`` blocks under
``spline.begin``.  Each block is one closed contour.  Printing them separately
shows whether a "merged" cross-section is really one rail body or several.

Usage: python dump_prr_sections.py [file.prr ...]
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(r"G:\研究生\动力学\CRH380A_纯刚性模型\database\database")


def parse(path: Path) -> list[list[tuple[float, float]]]:
    blocks: list[list[tuple[float, float]]] = []
    inside = False
    current: list[tuple[float, float]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s.startswith("point.begin"):
            inside, current = True, []
        elif s.startswith("point.end"):
            inside = False
            if current:
                blocks.append(current)
        elif inside and s and not s.startswith("#"):
            fields = s.split()
            if len(fields) >= 2:
                try:
                    current.append((float(fields[0]) * 1e3, float(fields[1]) * 1e3))
                except ValueError:
                    pass
    return blocks


def find(name: str) -> Path:
    hits = list(ROOT.rglob(name))
    if not hits:
        raise SystemExit(f"not found: {name}")
    return hits[0]


def main(argv: list[str]) -> int:
    names = argv[1:] or ["Profile_Mileage_R79.0286.prr", "Profile_Mileage_YG_DD_XG_DD.prr",
                         "Profile_Mileage_R80.0044.prr", "Profile_Mileage_XG_HH.prr"]
    for name in names:
        path = find(name)
        blocks = parse(path)
        print(f"=== {name}  ({len(blocks)} contour(s))  {path}")
        for k, block in enumerate(blocks):
            pts = block
            ys = [p[0] for p in pts]
            zs = [p[1] for p in pts]
            print(f"  contour {k}: n={len(pts)} y=[{min(ys):.2f},{max(ys):.2f}] z=[{min(zs):.2f},{max(zs):.2f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
