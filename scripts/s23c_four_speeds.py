"""Four steady speeds on one track: is the 27.5 mm feature rail geometry, and does its depth hold?

Two speeds gave one ratio, which cannot separate "the operator depends on speed" from "the two passes cover
different track".  Four speeds over the same sections can: a rail pitch keeps its wavelength, so its frequency
must sit at ``v / lambda`` on every pass, and the depth recovered from the short-wave constant must agree across
them if that constant is speed-independent.

Run:  python -X utf8 scripts/s23c_four_speeds.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import s23b_two_speeds as two

FOLDER = Path(r"F:\ai道岔状态反演辨识\75kmh数据")
WORK = Path(r"F:\velch_tmp\four_speeds")
CANDIDATES_MM = (27.5, 40.0, 60.0, 20.0)
MATCH_HZ = 2.0


def main() -> int:
    records = sorted(FOLDER.glob("Run_*kmh_*.mat"))
    if len(records) < 3:
        raise SystemExit(f"need at least three passes, found {[record.name for record in records]}")
    print(f"{len(records)} passes: " + ", ".join(record.name for record in records))

    results = {}
    for record in records:
        label = record.stem.replace(" (1)", "")
        try:
            results[label] = two.analyse(record, label)
        except SystemExit as error:
            print(f"  {label}: skipped ({error})")

    speeds = [payload["steady_speed_kmh"] for payload in results.values()]
    print("\nsteady speeds: " + ", ".join(f"{speed:.2f}" for speed in speeds))

    # Does a peak exist at v/lambda on every pass, in the same section?
    print(f"\n{'section':8s} " + " ".join(f"{label[:13]:>14s}" for label in results))
    presence = {wavelength: 0 for wavelength in CANDIDATES_MM}
    depth_rows = {wavelength: [] for wavelength in CANDIDATES_MM}
    for section in two.SECTION_KM:
        cells = []
        for label, payload in results.items():
            section_payload = payload["sections"].get(section) or {}
            if "peaks" not in section_payload:
                cells.append("      skipped")
                continue
            speed_m_s = payload["steady_speed_kmh"] / 3.6
            found = []
            for wavelength in CANDIDATES_MM:
                target = speed_m_s / (wavelength / 1000.0)
                peaks = [peak["frequency_hz"] for peak in section_payload["peaks"]]
                hit = bool(peaks) and min(abs(np.array(peaks) - target)) <= MATCH_HZ
                found.append("+" if hit else ".")
                if hit:
                    presence[wavelength] += 1
            # The stored amplitude is the coherent fit at the design wavelength (27.5 mm) for this pass.
            amplitude = section_payload["amplitude_m_per_s2"]
            depth_rows[CANDIDATES_MM[0]].append(
                amplitude / two.SHORT_WAVE_GAIN * 1e6)
            cells.append(f"{section_payload['design_frequency_hz']:7.1f}Hz {''.join(found)}")
        print(f"{section:8s} " + " ".join(f"{cell:>14s}" for cell in cells))

    print("\npeak present (of %d section-passes):" % (len(two.SECTION_KM) * len(results)))
    for wavelength in CANDIDATES_MM:
        print(f"  {wavelength:5.1f} mm: {presence[wavelength]:3d}")

    depths = np.array(depth_rows[CANDIDATES_MM[0]], dtype=float)
    print(f"\ndepth at {CANDIDATES_MM[0]:.1f} mm per pass (um): "
          + ", ".join(f"{value:.1f}" for value in depths))
    if depths.size:
        print(f"  median {np.median(depths):.1f} um, min {depths.min():.1f}, max {depths.max():.1f}, "
              f"max/min {depths.max() / max(depths.min(), 1e-9):.1f}")

    # The operator's own prediction: a = (2 pi f_n)^2 A is speed independent, so the depths must agree.
    verdict = ("speed independent within a factor of two"
               if depths.size and depths.max() / max(depths.min(), 1e-9) <= 2.0
               else "NOT speed independent: the depth moves by more than a factor of two between passes")
    print(f"\nverdict: {verdict}")

    WORK.mkdir(parents=True, exist_ok=True)
    payload = {"passes": {label: {"steady_speed_kmh": results[label]["steady_speed_kmh"],
                                  "steady_seconds": results[label]["steady_seconds"],
                                  "sections": results[label]["sections"]}
                          for label in results},
               "presence": {f"{wavelength:.1f}mm": presence[wavelength] for wavelength in CANDIDATES_MM},
               "depths_um": depths.tolist(), "verdict": verdict}
    target = WORK / "four_speeds.json"
    target.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"written {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
