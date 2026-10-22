"""Inspect the raw measured folders: recursive file counts, names, and first rows."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(r"E:\齿轨测试数据\轮轨力和位移采集")
TARGETS = ("25kmh-SP-1", "30kmh", "10kmh-SP-3")


def peek(path: Path, rows: int = 3) -> None:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        head = [next(handle).strip() for _ in range(rows)]
    print(f"    {path.name}  {path.stat().st_size / 1e6:7.1f} MB")
    for line in head:
        print(f"      {line[:110]}")


def main() -> int:
    for name in TARGETS:
        folder = ROOT / name
        print(f"\n== {name} ==")
        if not folder.is_dir():
            print("  missing")
            continue
        direct = sorted(folder.glob("*.txt"))
        nested = sorted(folder.rglob("*.txt"))
        print(f"  direct txt {len(direct)}, recursive txt {len(nested)}")
        subdirs = sorted(p for p in folder.iterdir() if p.is_dir())
        if subdirs:
            print(f"  subdirs ({len(subdirs)}): {[p.name for p in subdirs][:6]}")
            for sub in subdirs[:2]:
                files = sorted(sub.rglob("*.txt"))
                print(f"    {sub.name}: {len(files)} txt")
                for path in files[:3]:
                    peek(path)
        for path in direct[:3]:
            peek(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
