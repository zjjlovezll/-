"""Node count and spacing of the rail body sections the contact search sees."""

from __future__ import annotations

import csv
import glob
import pathlib

for path in sorted(glob.glob(r"bodies/*.csv"))[:4]:
    rows = [r for r in csv.reader(open(path, newline="")) if r]
    ys = []
    for r in rows:
        if not r or not r[0].strip():
            continue
        head = r[0].lstrip()
        if head.startswith("#") or head[0].isalpha():
            continue
        ys.append(float(r[0]))
    if not ys:
        print(f"{pathlib.Path(path).name}: header only")
        continue
    ys.sort()
    gaps = [(ys[i + 1] - ys[i]) * 1e3 for i in range(len(ys) - 1)]
    gaps.sort()
    span = (ys[-1] - ys[0]) * 1e3
    median = gaps[len(gaps) // 2] if gaps else float("nan")
    print(
        f"{pathlib.Path(path).name}: n={len(ys)} span={span:.2f} mm "
        f"median_dy={median:.4f} mm  (~{int(span / 0.5)} nodes at 0.5 mm)"
    )
