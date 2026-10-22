"""断面/布置图 DXF 探查工具（只读）。

用途：把 ODA File Converter 转出的 DXF 打开，先回答三个问题：
  1. 图上到底有哪些图层、各有多少实体；
  2. 所有文字（TEXT/MTEXT/ATTRIB/DIMENSION 文本）分别写了什么、插在哪个位置；
  3. 图形范围（extents）与线型单位。

不修改任何输入文件。

用法：
    python dxf_probe.py <drawing.dxf> [--dump-text <out.txt>] [--layers a,b]
"""

from __future__ import annotations

import argparse
import collections
import sys

import ezdxf
from ezdxf import recover


def open_dxf(path: str):
    try:
        return ezdxf.readfile(path), "normal"
    except Exception as exc:  # noqa: BLE001 - 需要把真实失败原因报出来
        print(f"[warn] ezdxf.readfile 失败（{type(exc).__name__}: {exc}），改用 recover", file=sys.stderr)
        doc, auditor = recover.readfile(path)
        print(f"[warn] recover: errors={len(auditor.errors)} fixes={len(auditor.fixes)}", file=sys.stderr)
        return doc, "recover"


def text_of(entity) -> str:
    kind = entity.dxftype()
    if kind == "MTEXT":
        return entity.plain_text()
    if kind == "TEXT":
        return entity.dxf.text
    if kind == "ATTRIB":
        return entity.dxf.text
    if kind == "DIMENSION":
        try:
            return entity.dxf.text
        except Exception:  # noqa: BLE001
            return ""
    return ""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--dump-text", default=None)
    ap.add_argument("--layers", default=None, help="只统计这些图层（逗号分隔）")
    args = ap.parse_args(argv)

    doc, mode = open_dxf(args.path)
    msp = doc.modelspace()

    layer_filter = set(args.layers.split(",")) if args.layers else None

    counts = collections.Counter()
    layer_counts = collections.Counter()
    for e in msp:
        kind = e.dxftype()
        counts[kind] += 1
        layer = e.dxf.get("layer", "0")
        if layer_filter is None or layer in layer_filter:
            layer_counts[(layer, kind)] += 1

    print(f"file      : {args.path}")
    print(f"open mode : {mode}")
    print(f"dxf ver   : {doc.dxfversion}  ({doc.acad_release})")
    print(f"units     : {doc.header.get('$INSUNITS', 'unset')}")
    print(f"entities  : {sum(counts.values())}")
    print("\n== entity types ==")
    for k, v in counts.most_common():
        print(f"{v:8d}  {k}")

    print("\n== layers x types (top 40) ==")
    for (layer, kind), v in layer_counts.most_common(40):
        print(f"{v:8d}  {layer:<28s} {kind}")

    print("\n== layers (name: color, entity count) ==")
    for layer in doc.layers:
        n = sum(1 for e in msp if e.dxf.get("layer", "0") == layer.dxf.name)
        if n:
            print(f"{n:8d}  {layer.dxf.name:<30s} color={layer.dxf.color}")

    texts = []
    for e in msp:
        if e.dxftype() in {"TEXT", "MTEXT", "ATTRIB", "DIMENSION"}:
            s = text_of(e).strip()
            if not s:
                continue
            try:
                p = e.dxf.insert
                x, y = float(p[0]), float(p[1])
            except Exception:  # noqa: BLE001
                x = y = float("nan")
            texts.append((x, y, e.dxf.get("layer", "0"), e.dxftype(), s))

    print(f"\n== text entities: {len(texts)} ==")
    for row in texts[:40]:
        print(f"  x={row[0]:12.3f} y={row[1]:10.3f} [{row[2]}] {row[4][:80]}")

    if args.dump_text:
        with open(args.dump_text, "w", encoding="utf-8") as fh:
            for x, y, layer, kind, s in sorted(texts, key=lambda r: (r[0], r[1])):
                fh.write(f"{x:14.4f}\t{y:14.4f}\t{layer}\t{kind}\t{s}\n")
        print(f"\n[ok] 文字已导出 -> {args.dump_text}")

    try:
        ext_min = doc.header.get("$EXTMIN")
        ext_max = doc.header.get("$EXTMAX")
        print(f"\n== extents ==\n  min {tuple(round(float(v), 3) for v in ext_min[:3])}"
              f"\n  max {tuple(round(float(v), 3) for v in ext_max[:3])}")
    except Exception as exc:  # noqa: BLE001
        print(f"\n[extents] 不可用: {exc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
