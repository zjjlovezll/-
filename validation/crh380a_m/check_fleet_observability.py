"""Is the theta signal observable in the waveform, even though the peak is not?

For each fleet case read the right-rail normal force history, take the central baseline
(fleet_01) as reference, and report the relative distance of each waveform from it.
If that distance is orders of magnitude above solver noise, the waveform -- not the peak
-- is the observable an inversion should use.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOTS = (Path(r"F:\velch_tmp\fleet"), Path(__file__).resolve().parent)
CHANNEL = "axle1_right_normal_n"


def load(root: Path):
    table = {}
    for path in sorted(root.glob("fleet_*/manifest.json")):
        case = path.parent.name
        history = path.parent / "history.csv"
        if not history.exists():
            continue
        with history.open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        table[case] = [float(row[CHANNEL]) for row in rows]
    return table


def main() -> int:
    for root in ROOTS:
        if not root.exists():
            continue
        table = load(root)
        if len(table) < 2:
            continue
        baseline = next((name for name in table if "k1.00" in name), sorted(table)[1])
        reference = table[baseline]
        print(f"root {root}   reference {baseline}   samples {len(reference)}")
        print(f"{'case':<28}{'peak kN':>9}{'mean kN':>9}{'rms vs ref kN':>15}{'rel':>9}")
        for name in sorted(table):
            series = table[name]
            count = min(len(series), len(reference))
            diff = [a - b for a, b in zip(series[:count], reference[:count])]
            rms = (sum(value * value for value in diff) / count) ** 0.5
            norm = (sum(value * value for value in reference[:count]) / count) ** 0.5
            print(f"{name:<28}{max(series) / 1e3:>9.1f}{sum(series) / len(series) / 1e3:>9.1f}"
                  f"{rms / 1e3:>15.3f}{rms / norm:>9.4f}")
        return 0
    print("no fleet histories found")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
