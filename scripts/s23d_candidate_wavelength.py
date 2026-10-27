"""Ask one wavelength, one block length: is there a resolved line, and does its depth hold across speeds?

The four-speed scan found no wavelength with a peak in most section-passes at 1.02 s blocks, and 60 mm was the
only candidate present at more than a few.  Two knobs could still be hiding a real line: the wavelength asked
about, and the frequency resolution (1.02 s blocks smear a narrow line into the neighbouring bins).  This script
takes both as arguments so the same question can be asked without editing constants.

Run:  python -X utf8 scripts/s23d_candidate_wavelength.py --wavelength-mm 60 --block 8192
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import s23b_two_speeds as two

FOLDER = Path(r"F:\ai道岔状态反演辨识\75kmh数据")
WORK = Path(r"F:\velch_tmp\candidate")
MATCH_HZ = 2.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wavelength-mm", type=float, default=27.5)
    parser.add_argument("--block", type=int, default=4096)
    parser.add_argument("--match-hz", type=float, default=MATCH_HZ)
    parser.add_argument("--json", type=Path, default=None)
    arguments = parser.parse_args()

    wavelength_m = arguments.wavelength_mm / 1000.0
    two.BLOCK = int(arguments.block)
    two.DESIGN_WAVELENGTH_M = wavelength_m
    resolution_hz = two.RATE_HZ / arguments.block
    print(f"wavelength {arguments.wavelength_mm:.2f} mm, block {arguments.block} "
          f"({arguments.block / two.RATE_HZ:.2f} s, resolution {resolution_hz:.3f} Hz), "
          f"match window +-{arguments.match_hz:.2f} Hz")

    records = sorted(FOLDER.glob("Run_*kmh_*.mat"))
    results = {}
    for record in records:
        label = record.stem.replace(" (1)", "")
        results[label] = two.analyse(record, label)

    print("\nper section: design frequency, whether a peak sits inside the match window, and the depth")
    print(f"{'section':8s} " + " ".join(f"{label[:13]:>20s}" for label in results))
    hits = 0
    depths = []
    table = {}
    for section in two.SECTION_KM:
        cells = []
        table[section] = {}
        for label, payload in results.items():
            section_payload = payload["sections"].get(section) or {}
            if "peaks" not in section_payload:
                cells.append("             skipped")
                continue
            target = section_payload["design_frequency_hz"]
            peaks = [peak["frequency_hz"] for peak in section_payload["peaks"]]
            gap = min(abs(np.array(peaks) - target)) if peaks else float("inf")
            found = gap <= arguments.match_hz
            hits += int(found)
            depth = section_payload["depth_um"]
            depths.append(depth)
            table[section][label] = {"design_hz": target, "nearest_peak_gap_hz": float(gap),
                                     "present": bool(found), "depth_um": depth}
            cells.append(f"{target:7.1f}Hz {'+' if found else '.'} {depth:6.1f}um")
        print(f"{section:8s} " + " ".join(f"{cell:>20s}" for cell in cells))

    total = sum(len([cell for cell in payload["sections"].values() if "peaks" in cell])
                for payload in results.values())
    depths_array = np.array(depths, dtype=float)
    print(f"\npeaks inside the window: {hits} of {total} section-passes")
    if depths_array.size:
        print(f"depth: median {np.median(depths_array):.1f} um, min {depths_array.min():.1f}, "
              f"max {depths_array.max():.1f}, spread {depths_array.max() / max(depths_array.min(), 1e-9):.1f}x")

    # A quantitative claim needs both a line and agreeing depths; report which of the two fails.
    present = [row for section in table.values() for row in section.values() if row["present"]]
    quantifiable = False
    if present:
        values = np.array([row["depth_um"] for row in present], dtype=float)
        quantifiable = bool(values.size >= 3 and values.max() / max(values.min(), 1e-9) <= 2.0)
        print(f"depth where the line IS present: " + ", ".join(f"{value:.1f}" for value in values)
              + f" um (spread {values.max() / max(values.min(), 1e-9):.1f}x)")
    verdict = ("quantifiable: a line exists and the depth agrees within a factor of two"
               if quantifiable else
               "not quantifiable: " + ("too few section-passes carry the line" if hits < 3
                                        else "the depth where the line exists disagrees by more than 2x"))
    print(f"verdict: {verdict}")

    WORK.mkdir(parents=True, exist_ok=True)
    target = arguments.json or WORK / f"candidate_{arguments.wavelength_mm:g}mm_{arguments.block}.json"
    target.write_text(json.dumps({
        "wavelength_mm": arguments.wavelength_mm, "block": arguments.block,
        "resolution_hz": resolution_hz, "match_hz": arguments.match_hz,
        "hits": hits, "total": total, "table": table, "verdict": verdict,
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"written {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
