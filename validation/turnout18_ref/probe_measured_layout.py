"""List the measured campaign layout for the 30 km/h uphill runs."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(r"E:\齿轨测试数据")
SUBDIR = "轮轨力和位移采集"

target = ROOT / SUBDIR
print(f"exists {target} -> {target.exists()}")
names = sorted(p.name for p in target.iterdir() if p.is_dir())
print(f"directories ({len(names)}):")
for name in names:
    print(f"  {name}")

for candidate in names:
    if "30" in candidate and "SP" in candidate.upper():
        folder = target / candidate
        files = sorted(p.name for p in folder.glob("*.txt"))
        print(f"\n{candidate}: {len(files)} txt")
        for f in files[:3]:
            print(f"  {f}")
        if files:
            sample = folder / files[0]
            with sample.open("r", encoding="utf-8", errors="replace") as handle:
                for index, line in enumerate(handle):
                    if index >= 3:
                        break
                    print(f"  line{index}: {line.strip()[:80]}")
