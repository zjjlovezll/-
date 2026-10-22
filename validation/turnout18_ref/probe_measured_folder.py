"""Inspect the 30 km/h folder, one 5 km/h folder, and the campaign windows table."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(r"E:\齿轨测试数据")
MEASURED = ROOT / "轮轨力和位移采集"
PIPELINE = ROOT / "实测数据出图代码"

for name in ("30kmh", "5kmh上坡"):
    folder = MEASURED / name
    files = sorted(p.name for p in folder.glob("*.txt"))
    print(f"\n{name}: {len(files)} txt")
    for f in files:
        print(f"  {f}")
    if files:
        with (folder / files[0]).open("r", encoding="utf-8", errors="replace") as handle:
            for index, line in enumerate(handle):
                if index >= 2:
                    break
                print(f"  line{index}: {line.strip()[:70]}")

table = PIPELINE / "condition_windows.csv"
print(f"\ncondition_windows.csv exists {table.exists()}")
if table.exists():
    lines = table.read_text(encoding="utf-8-sig").splitlines()
    print(f"  rows {len(lines)}")
    for line in lines[:8]:
        print(f"  {line}")
