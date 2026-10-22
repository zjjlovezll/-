"""Print recorded wall times from run and batch manifests."""

from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent

for name in ("out_AA_frog2l", "out_AA_full2l", "out_AA_w4"):
    path = ROOT / name / "manifest.json"
    if not path.exists():
        print(f"{name:18s} (no manifest)")
        continue
    text = path.read_text(encoding="utf-8")
    walls = re.findall(r'"wall_s":\s*([0-9.]+)', text)
    nfev = re.findall(r'"nfev":\s*([0-9]+)', text)
    print(f"{name:18s} wall_s={walls} nfev={nfev}")

batch = ROOT / "out_AA_batch8"
if batch.exists():
    files = sorted(batch.rglob("batch*.json")) or sorted(batch.glob("*.json"))
    for path in files:
        text = path.read_text(encoding="utf-8")
        walls = re.findall(r'"wall_s":\s*([0-9.]+)', text)
        print(f"{path.name:18s} n={len(walls)} walls={walls}")
