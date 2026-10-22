"""Are SDITT turnout profiles expressed in the turnout's global transverse frame?

If yes, a part's own y values already contain its lateral placement, and a diverging-route catalog can
be assembled by simply stacking the parts' profile series -- no invented offsets.
"""

from __future__ import annotations

import re
from pathlib import Path

from velch.profiles import load_profile

ROOT = Path(r"G:\研究生\SDITT-RW-FT-250728\SDITT-RW-FT-250728\WRProfile-07(009)-1_18")

SAMPLES = [
    ("曲基本轨 qjbg @50.000", "07(009)-qjbg-20200418/07(009)-qjbg-20200418-0.prr"),
    ("曲基本轨 qjbg @60.943", "07(009)-qjbg-20200418/07(009)-qjbg-20200418-72.prr"),
    ("长心轨 cxg @103.280", "07(009)-cxg-20250801/07(009)-cxg-20250801-12.5.prr"),
    ("长心轨 cxg @116.440", "07(009)-cxg-20250801/07(009)-cxg-20250801-H.prr"),
]


def main() -> None:
    for label, relative in SAMPLES:
        path = ROOT / relative
        if not path.exists():
            print(f"{label:<26} MISSING {relative}")
            continue
        for surface in ("rail_top",):
            graph = load_profile(path, file_format="prr", surface=surface)
            y_mm = graph.y_m * 1000.0
            z_mm = graph.z_m * 1000.0
            print(f"{label:<26} n={y_mm.size:>5} "
                  f"y=[{y_mm.min():8.2f},{y_mm.max():8.2f}] "
                  f"z=[{z_mm.min():7.2f},{z_mm.max():7.2f}] mm")
    # a through-route part for comparison
    for relative in ("07(009)-zjg-20200418", "07(009)-zgyg-20250722"):
        folder = ROOT / relative
        files = sorted(p for p in folder.glob("*.prr"))
        if not files:
            continue
        for pick in (files[0], files[len(files) // 2], files[-1]):
            graph = load_profile(pick, file_format="prr", surface="rail_top")
            y_mm = graph.y_m * 1000.0
            print(f"{relative:<22} {pick.name:<34} y=[{y_mm.min():8.2f},{y_mm.max():8.2f}] mm")

    # key profiles footer / header lines that carry placement data
    key = ROOT / "07(009)-qjbg-20200418" / "Key profiles"
    if key.exists():
        print(f"\nKey profiles bytes: {key.stat().st_size}")


if __name__ == "__main__":
    main()
