"""Shape probe of the SDITT turnout catalog (keys only, no bulk printing)."""

from __future__ import annotations

import json
from pathlib import Path

CATALOG = Path(__file__).with_name("sditt_turnout_catalog.json")

data = json.loads(CATALOG.read_text(encoding="utf-8"))
print("turnout       :", data.get("turnout"))
print("summary       :", data.get("summary"))
print("inventory     :", {k: sorted(v) for k, v in data["parts"].items()})

stations = data["stations"]
sample_key = "53.082"
sample = stations[sample_key]
print("station parts :", sorted(sample))
record = sample["qjbg"]
print("part record   :", record)

# where each part appears
spans: dict[str, list[float]] = {}
for key, station in stations.items():
    for name in station:
        spans.setdefault(name, []).append(float(key))
for name, values in sorted(spans.items()):
    print(f"  {name:<12} {len(values):>3} stations  {min(values):8.3f} .. {max(values):8.3f} m")
