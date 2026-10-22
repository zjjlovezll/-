"""Walk 轮轨力和位移采集\30kmh two levels deep to find the 30 km/h force files."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(r"E:\齿轨测试数据") / "轮轨力和位移采集"
TARGET = ROOT / "30kmh"

print(f"exists {TARGET.exists()}")
for entry in sorted(TARGET.iterdir()):
    kind = "dir" if entry.is_dir() else "file"
    print(f"  {kind:<4} {entry.name}")
    if entry.is_dir():
        children = sorted(entry.iterdir())
        print(f"        {len(children)} entries")
        for child in children[:4]:
            size = child.stat().st_size if child.is_file() else 0
            print(f"        - {child.name} ({size} B)")
