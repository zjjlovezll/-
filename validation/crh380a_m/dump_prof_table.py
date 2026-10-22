"""Dump the Simpack rail-profile table: file <-> mileage, plus the frog window."""
from __future__ import annotations

import re
from pathlib import Path

P = Path(r"G:\研究生\动力学\CRH380A_纯刚性模型\database\database\mbs_db_substructure\CRH380A_M_Wheelset.spck")


def main() -> None:
    lines = P.read_text(encoding="utf-8", errors="replace").splitlines()
    files: dict[int, str] = {}
    mil: dict[int, float] = {}
    for line in lines:
        m = re.match(r"\s*rail\.r\.prof\.file\s*\(\s*(\d+)\s*,.*?\)\s*=\s*'([^']+)'", line)
        if m:
            files[int(m.group(1))] = m.group(2)
        m = re.match(r"\s*rail\.r\.prof\.s\s*\(\s*(\d+)\s*,.*?\)\s*=\s*([-0-9.eE+]+)", line)
        if m:
            mil[int(m.group(1))] = float(m.group(2))
    print(f"files={len(files)} mileage={len(mil)}")
    for i in range(150, 176):
        print(f"{i:4d} s={mil.get(i, float('nan')):9.4f}  {files.get(i)}")
    for target in (79.131, 79.440, 80.004, 80.278, 80.911):
        best = min(mil.items(), key=lambda kv: abs(kv[1] - target))
        print(f"nearest to {target:7.3f}: idx {best[0]:3d} s={best[1]:8.4f} {files.get(best[0])}")


if __name__ == "__main__":
    main()
