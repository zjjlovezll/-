"""Build a portable model bundle: the referenced assets, and cases that name them relatively.

A corpus case today references its wheel/rail profiles and ``.tre`` records by absolute path
(``G:\\研究生\\...``, ``H:\\不平顺\\...``).  That works on exactly one machine.  The whole corpus is
916 MB of unique assets across 13 447 files — too much to ship — but the reference set is not:
the two turnout cases that carry the frozen baselines need **318 files / 13.0 MB**, and they share
all of them.

So this script copies only what the chosen cases actually name, de-duplicates by content hash,
and rewrites each case so every reference is a plain relative name inside the bundle.  The result
is a folder that survives being zipped, copied to another disk, or moved into an installer.

Usage::

    python -X utf8 packaging/portable_models.py            # build the default preset
    python -X utf8 packaging/portable_models.py --verify   # only check an existing bundle
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

PRESET = ("case_frog_N_strip05.json", "case_full12_cap05.json", "case_A_final_law.json")
REFERENCE_KEYS = ("file", "tre", "modal_file")
TARGET = ROOT / "portable" / "validation" / "crh380a_m"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _collect(node, found: list[str]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key in REFERENCE_KEYS and isinstance(value, str):
                found.append(value)
            else:
                _collect(value, found)
    elif isinstance(node, list):
        for item in node:
            _collect(item, found)


def _corpus() -> Path:
    from velch.data_root import case_dir

    return case_dir()


def build(target: Path = TARGET, names: tuple[str, ...] = PRESET) -> dict:
    source = _corpus()
    if not source.is_dir():
        raise SystemExit(f"no corpus at {source}: set VELCH_DATA_ROOT or write the marker file")
    marker = target / "BUNDLE.json"
    if target.exists():
        # ``--target`` is a command-line argument, and this line deletes whatever it points
        # at.  Only replace a directory that is recognisably ours: a mistyped target must
        # not take the corpus with it, and nothing here is in version control.
        if not marker.is_file() and any(target.iterdir()):
            raise SystemExit(
                f"refusing to replace {target}: it is not empty and holds no {marker.name}. "
                f"Pass --target pointing at a bundle directory, or empty it by hand.")
    assets_dir = target / "profiles"
    assets_dir.mkdir(parents=True)

    by_hash: dict[str, str] = {}
    rewritten: list[dict] = []
    total = 0

    for name in names:
        case_path = source / name
        if not case_path.is_file():
            raise SystemExit(f"missing case {case_path}")
        payload = json.loads(case_path.read_text(encoding="utf-8-sig"))
        refs: list[str] = []
        _collect(payload, refs)
        mapping: dict[str, str] = {}
        for ref in sorted(set(refs)):
            original = Path(ref)
            if not original.is_absolute():
                original = case_path.parent / ref
            original = original.resolve()
            if not original.is_file():
                raise SystemExit(f"{name} names a file that does not exist: {original}")
            digest = _sha(original)
            existing = by_hash.get(digest)
            if existing is None:
                local = original.name
                while (assets_dir / local).exists():
                    local = f"{original.stem}_{digest[:8]}{original.suffix}"
                shutil.copy2(original, assets_dir / local)
                by_hash[digest] = local
                existing = local
                total += original.stat().st_size
            mapping[ref] = f"profiles/{existing}"

        def rewrite(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in REFERENCE_KEYS and isinstance(value, str):
                        node[key] = mapping[value]
                    else:
                        rewrite(value)
            elif isinstance(node, list):
                for item in node:
                    rewrite(item)

        rewrite(payload)
        out = target / name
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        rewritten.append({"case": name, "assets": len(mapping), "bytes": out.stat().st_size})

    readme = (
        "可移植模型包\n"
        "============\n\n"
        "这里的三份算例与 `profiles/` 下的型面、不平顺记录，来自本机语料库的一次相对化导出。\n"
        "每个算例里的引用都已改成相对算例文件的 `profiles/...`，所以整个文件夹可以随便搬。\n\n"
        "用法（打包版或源码版都一样）：\n"
        "  velch run-vehicle <本目录>/case_frog_N_strip05.json --output out --fast\n\n"
        "把本目录的上一层（`validation`）设给 VELCH_DATA_ROOT，界面里的算例表就会列出这些算例。\n"
    )
    (target / "README.txt").write_text(readme, encoding="utf-8")
    manifest = {
        "cases": rewritten,
        "assets": len(by_hash),
        "asset_bytes": total,
        "source": str(source),
    }
    (target / "BUNDLE.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def verify(target: Path = TARGET) -> int:
    from velch.vehicle import load_vehicle_case

    if not target.is_dir():
        raise SystemExit(f"no bundle at {target}")
    failures = 0
    for case in sorted(target.glob("case_*.json")):
        try:
            loaded = load_vehicle_case(case)
        except Exception as error:  # noqa: BLE001 - the point is to report, not to raise
            failures += 1
            print(f"[FAIL] {case.name}: {type(error).__name__}: {error}")
            continue
        print(f"[PASS] {case.name}: {len(loaded.initial_q)} 坐标, "
              f"{len(loaded.asset_hashes)} 个资产, {len(loaded.wheels)} 个车轮")
    print(f"verdict: {'ACCEPT' if failures == 0 else 'REJECT'} · {failures} 处失败")
    return 0 if failures == 0 else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default=str(TARGET))
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--keep", action="store_true", help="verify without rebuilding")
    args = parser.parse_args()
    target = Path(args.target)
    if args.verify or args.keep:
        return verify(target)
    manifest = build(target)
    print(f"bundle: {target}")
    for item in manifest["cases"]:
        print(f"  {item['case']}: {item['assets']} 个引用 → {item['bytes']} 字节")
    print(f"  资产 {manifest['assets']} 个，{manifest['asset_bytes'] / 1e6:.1f} MB")
    return verify(target)


if __name__ == "__main__":
    raise SystemExit(main())
