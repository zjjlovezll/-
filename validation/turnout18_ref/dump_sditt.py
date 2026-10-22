"""Convert GBK-encoded SDITT .m files to UTF-8 copies so they can be read normally.

SDITT ships on a Chinese Windows machine: the .m sources are GB18030/GBK, which the read tool
refuses as invalid UTF-8.  We never modify the originals -- copies land in sditt_dump/.
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(r"G:\研究生\SDITT-RW-FT-250728\SDITT-RW-FT-250728")
OUT = Path(__file__).resolve().parent / "sditt_dump"

NAMES = [
    "SDITT_CR400_NoStrTIrr_250728_Face.m",
    "Matrix_FT_v2.m",
    "WR_Force_FT.m",
    "RailDyn_FT.m",
    "Get_Profile_P1_Through_CN18_250813.m",
    "Get_Profile_P1_Through_210624.m",
    "Get_FEM_Rail_P1_Through.m",
    "Get_FEM_Rail_P1_Diverging.m",
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        source = SRC / name
        if not source.exists():
            print(f"missing: {name}")
            continue
        raw = source.read_bytes()
        for encoding in ("gb18030", "utf-8", "latin-1"):
            try:
                text = raw.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:  # pragma: no cover - latin-1 never fails
            raise SystemExit(f"cannot decode {name}")
        target = OUT / name
        target.write_text(text, encoding="utf-8")
        print(f"{name:<46} {len(raw):>8} B  {encoding:<8} -> {len(text.splitlines()):>5} lines")


if __name__ == "__main__":
    main()
