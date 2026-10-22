"""Unit and metric anchors for every campaign channel family."""

from __future__ import annotations

import csv
from pathlib import Path

PATH = Path(r"E:\齿轨测试数据\实测数据出图代码\channel_quality_and_metrics.csv")
rows = list(csv.DictReader(PATH.read_text(encoding="utf-8-sig").splitlines()))
print(f"rows {len(rows)}")

families: dict[tuple[str, str], dict[str, object]] = {}
for row in rows:
    key = (row["role"], row["unit"])
    families.setdefault(key, {"n": 0, "peak": 0.0, "p999": 0.0, "fs": set()})
    entry = families[key]
    entry["n"] = int(entry["n"]) + 1
    entry["peak"] = max(float(entry["peak"]), float(row["event_abs_peak"]))
    entry["p999"] = max(float(entry["p999"]), float(row["event_abs_p999"]))
    entry["fs"].add(row["fs_hz"])
for (role, unit), entry in sorted(families.items()):
    print(f"{role:<10} unit {unit:<6} rows {entry['n']:>3}  "
          f"max|peak| {entry['peak']:10.4f}  max p99.9 {entry['p999']:10.4f}  "
          f"fs {','.join(sorted(entry['fs']))}")

print("\nacceleration channels of 30KMH-SP-1:")
for row in rows:
    if row["folder"].lower().startswith("30kmh-sp-1") and row["role"] != "force":
        print(f"  CH{row['channel']:>2} {row['role']:<10} {row['unit']:<5} "
              f"peak {float(row['event_abs_peak']):8.4f} p99.9 {float(row['event_abs_p999']):8.4f} "
              f"rms {float(row['event_rms']):8.4f}")
