"""Print the 07(009) turnout cross-section anatomy from the SDITT catalog.

Goal: show, station by station, which rail parts coexist and where they sit laterally.  That is the
evidence needed before the diverging route can be assembled -- our own Simpack catalog could not do it
because its left rail had only two stations (plain JBG) and the right rail was one merged series.
"""

from __future__ import annotations

import json
from pathlib import Path

CATALOG = Path(__file__).resolve().parent / "sditt_turnout_catalog.json"

PROBES = (50.578, 53.0, 56.0, 58.0, 60.943, 65.0, 70.0, 80.0, 90.0,
          100.0, 103.3, 105.0, 108.0, 112.0, 116.44)

PARTS_ZH = {
    "zjbg": "直基本轨",
    "qjbg": "曲基本轨",
    "zjg_zgyg": "直尖轨+直股引轨",
    "qjg_cgyg": "曲尖轨+曲股引轨",
    "cxg": "长心轨",
    "dxg": "短心轨",
    "cgjg": "岔跟尖轨",
    "hg": "护轨",
}


def main() -> None:
    payload = json.loads(CATALOG.read_text(encoding="utf-8"))
    stations = {float(key): table for key, table in payload["stations"].items()}
    keys = sorted(stations)
    print(f"catalog stations: {len(keys)}  span {keys[0]:.3f} .. {keys[-1]:.3f} m\n")

    print(" station | parts present (y extent mm)                                    ")
    print("---------+-----------------------------------------------------------------")
    for probe in PROBES:
        nearest = min(keys, key=lambda value: abs(value - probe))
        table = stations[nearest]
        cells = []
        for part in sorted(table):
            span = table[part]["y_mm"]
            name = PARTS_ZH.get(part.split("_2")[0], part)
            cells.append(f"{part}({name}) [{span[0]:.0f},{span[1]:.0f}]")
        print(f"{nearest:8.3f} | {len(table)} part(s): " + "; ".join(cells))

    # which part covers the longest mileage, and where the hand-over stations are
    print("\npart spans from the raw mileage maps:")
    for part, info in sorted(payload["parts"].items()):
        values = [s for s, _ in info["stations"]]
        print(f"  {part:<20} {len(values):>3} stations {min(values):8.3f} .. {max(values):8.3f} m")


if __name__ == "__main__":
    main()
