"""Read the campaign's own metrics tables to recover the acceleration unit and limits."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(r"E:\齿轨测试数据\实测数据出图代码")
for name in ("高频单轮轴响应指标.csv", "channel_quality_and_metrics.csv"):
    path = ROOT / name
    if not path.exists():
        print(f"{name}: missing")
        continue
    text = None
    for encoding in ("utf-8-sig", "gbk", "utf-8"):
        try:
            text = path.read_text(encoding=encoding)
            print(f"\n=== {name} ({encoding}) ===")
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        print(f"{name}: undecodable")
        continue
    rows = list(csv.reader(text.splitlines()))
    print(f"rows {len(rows)}  columns {len(rows[0])}")
    print("header:", rows[0])
    for row in rows[1:3]:
        print("row   :", row)
