"""Inventory the rack-turnout case: Simpack model, its exported result files, and the two raw
measured trees.  Read-only.

This file holds Chinese path literals, so it must stay UTF-8 and be run with ``python -X utf8``;
never rewrite it through PowerShell text cmdlets (they decode as ANSI and mangle the paths).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

MODEL = Path(r"H:\总的齿轨项目\总和1\直逆_修改降低值后设计 -上坡度\RACK_RAILWAY_VEHICLE - XNEW - M"
             r"\main_model\VEH_GEAR0_FX_STR_RACKN_QY-Re1_cjy_whcl_zn_TE_USERFORCE_CG_120.spck")
OUTPUT_DIR = Path(r"H:\齿轨工况\坡度工况\matlab\VEH_GEAR0_FX_STR_RACKN_QY-Re1_cjy_whcl_zn_TE_USERFORCE_CG_120.output")
RESULT_FILES = [
    OUTPUT_DIR / "NoExt_zgzn_jdz6.2mm_SP_00_3d.mat",
    OUTPUT_DIR / "NoExt_zgzn_jdz6.2mm_SP_00_3d.sbr",
    OUTPUT_DIR / "NoExt_zgzn_jdz6.2mm_SP_00.mat",
    OUTPUT_DIR / "NoExt_zgzn_jdz6.2mm_SP_00.sbr",
]
MEASURED = [Path(r"E:\齿轨测试数据\轮轨力和位移采集"), Path(r"E:\齿轨测试数据\加速度采集")]


def show(path: Path) -> None:
    if not path.exists():
        print(f"MISSING {path}")
        return
    stat = path.stat()
    stamp = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
    print(f"{path.name:<58} {stat.st_size / 1e6:9.2f} MB  {stamp}")


def main() -> int:
    print("== Simpack model ==")
    show(MODEL)

    print("\n== exported result files ==")
    for path in RESULT_FILES:
        show(path)
    if OUTPUT_DIR.exists():
        others = sorted(p for p in OUTPUT_DIR.iterdir() if p.is_file())
        print(f"\ndirectory holds {len(others)} files; first 12 by name:")
        for path in others[:12]:
            show(path)

    print("\n== measured raw trees ==")
    for root in MEASURED:
        if not root.exists():
            print(f"MISSING {root}")
            continue
        conditions = sorted(p for p in root.iterdir() if p.is_dir())
        print(f"{root}  -> {len(conditions)} condition folders")
        for folder in conditions:
            files = sorted(folder.glob("*.txt"))
            total = sum(p.stat().st_size for p in files) / 1e6
            print(f"  {folder.name:<34} {len(files):>3} txt  {total:8.1f} MB")

    payload = {
        "model": str(MODEL), "model_exists": MODEL.exists(),
        "result_files": [{"path": str(p), "exists": p.exists(),
                          "size_bytes": p.stat().st_size if p.exists() else None}
                         for p in RESULT_FILES],
        "output_dir_files": len(list(OUTPUT_DIR.glob("*"))) if OUTPUT_DIR.exists() else None,
        "measured": [{"root": str(r), "exists": r.exists(),
                      "conditions": [p.name for p in sorted(r.iterdir()) if p.is_dir()]
                      if r.exists() else []} for r in MEASURED],
    }
    Path("rack_case_inventory.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
