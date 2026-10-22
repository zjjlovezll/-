"""Print the segmented rail bodies across the frog from the body catalog.

Answers one question with numbers: at which lateral positions the raw section
carries running surface between 79.7 and 80.5 m, i.e. whether anything at all
sits under the wheel reference plane (746.5 mm) there.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

DEFAULT = Path(__file__).with_name("turnout_bodies_raw.json")


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else DEFAULT
    lo = float(argv[2]) if len(argv) > 2 else 79.7
    hi = float(argv[3]) if len(argv) > 3 else 80.5
    data = json.loads(path.read_text(encoding="utf-8"))
    stations = data["stations"] if isinstance(data, dict) else data
    rows = [item for item in stations if lo <= float(item["s_m"]) <= hi]
    print(f"{'s_m':>8s} {'nb':>2s}  bodies: y_lo..y_hi crown_y crown_z_mm width_mm")
    for item in sorted(rows, key=lambda r: float(r["s_m"])):
        parts = []
        for body in item["bodies"]:
            parts.append(f"{body['y_lo_m'] * 1e3:5.0f}..{body['y_hi_m'] * 1e3:5.0f} "
                         f"c={body['crown_y_m'] * 1e3:5.0f} z={body['crown_z_m'] * 1e3:+6.2f} "
                         f"w={body['width_m'] * 1e3:5.1f}")
        print(f"{float(item['s_m']):8.3f} {item['n_bodies']:2d}  " + " | ".join(parts))
    in_band = [item for item in rows
               if any(0.736 <= body["crown_y_m"] <= 0.790 and body["crown_z_m"] > -0.001
                      for body in item["bodies"])]
    print(f"\nstations {lo}-{hi} m: {len(rows)}; with a crown in y 736-790 mm at z>-1 um: "
          f"{len(in_band)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
