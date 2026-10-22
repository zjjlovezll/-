"""对比 Simpack 实跑模型（model.spck 副本）与 Velch 采集的型面站位映射。

目的：回答“同样的断面，为什么 Simpack 不出现 600 kN”。
如果两者的 (s -> PRR 文件) 映射不同，则输入几何不同，问题在采集；
如果完全相同，则差异在求解器的接触/采样方式。
"""

from __future__ import annotations

import json
import os
import re
import sys

SIDES = ("left", "right")


def decode_spck(path: str) -> str:
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-8", "utf-16", "gbk", "latin-1"):
        try:
            text = raw.decode(enc)
        except Exception:
            continue
        if "prof" in text:
            return text
    raise SystemExit("cannot decode " + path)


def profile_map(text: str, side: str) -> dict[int, tuple[float, str]]:
    pat_s = re.compile(rf"rail\.{side}\.prof\.s\((\d+)\)\s*=\s*([-0-9.eE+]+)")
    pat_f = re.compile(rf'rail\.{side}\.prof\.file\((\d+)\)\s*=\s*((?:"[^"]*")|[^\r\n]*)')
    s = {int(m.group(1)): float(m.group(2)) for m in pat_s.finditer(text)}
    f = {int(m.group(1)): m.group(2).strip().strip('"') for m in pat_f.finditer(text)}
    return {k: (s[k], os.path.basename(f.get(k, ""))) for k in sorted(s)}


def main() -> None:
    spck = sys.argv[1]
    catalog = sys.argv[2]
    text = decode_spck(spck)
    cat = json.load(open(catalog, encoding="utf-8"))
    refs = cat["profile_references"]

    for side in SIDES:
        sp = profile_map(text, side)
        cl = [
            (float(r["s_m"]), os.path.basename(r["profile"]["file"]))
            for r in refs.get(side, [])
        ]
        cl_by_s = {round(s, 6): f for s, f in cl}
        print(f"=== {side}: spck {len(sp)} 条, catalog {len(cl)} 条 ===")
        if side != "right":
            continue
        diffs = 0
        print("   spck_s     spck_file                     catalog_file                  flag")
        for idx, (s, fname) in sp.items():
            cf = cl_by_s.get(round(s, 6))
            if cf is None:
                print(f"  {s:10.4f}  {fname:28s}  {'(缺失)':28s}  AD")
                diffs += 1
                continue
            if cf != fname:
                diffs += 1
                print(f"  {s:10.4f}  {fname:28s}  {cf:28s}  DIFF")
        extra = set(cl_by_s) - {round(s, 6) for s in sp}
        print(f"  映射不同 {diffs} 处；catalog 多出 {len(extra)} 条")
        if extra:
            print("  catalog 多出站位:", sorted(extra)[:10])
        print()
        lo, hi = 78.0, 82.0
        print(f"  {lo}–{hi} m 段并排：")
        print("   spck_s     spck_file                     catalog_s   catalog_file")
        for idx, (s, fname) in sp.items():
            if lo <= s <= hi:
                cf = cl_by_s.get(round(s, 6))
                cs = s if cf is not None else None
                print(f"  {s:10.4f}  {fname:28s}  {cs}  {cf}")


if __name__ == "__main__":
    main()
