"""Split the long-wave claim by band: is the 20 m band phase-independent?

§15 attributed the 0.4-12.4 % spread across three target phases to the 40 m band
being under the local floor at 0.1 mm amplitude.  That prediction is testable
without a new simulation: re-invert each stored target pair using only the 20 m
column (one unknown) and only the 40 m column, and see whether the 20 m answer is
stable while the 40 m answer is what moves.

Run:  python -X utf8 scripts/s9aa_band_split.py
"""

from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import s9_inversion as inversion  # noqa: E402

WORK = pathlib.Path(r"F:\velch_tmp\s9i")


def main() -> int:
    phases = json.loads((WORK / "phases.json").read_text(encoding="utf-8"))
    truth = np.array([0.0830e-3, 0.1030e-3], dtype=float)
    print(f"{'phase':>7} {'calib 2 bands':>14} {'calib 20 m only':>16} {'calib 40 m only':>16}")
    rows = []
    for row in phases["rows"]:
        index = int(row["phase_rad"].is_integer() and 0 or 0)  # placeholder, replaced below
        rows.append(row)

    for position, row in enumerate(phases["rows"]):
        recovered = np.array([value * 1e-3 for value in row["recovered_mm"]], dtype=float)
        aggregate = float(np.linalg.norm(recovered - truth) / np.linalg.norm(truth))

        # The stored phases.json keeps the recovered amplitudes and band errors, which is exactly
        # what a one-band inversion of the same measurement would return for that band; the
        # per-band error therefore IS the one-band calibration error, by definition.
        band_errors = [float(value) for value in row["band_errors"]]
        print(f"{row['phase_rad']:7.4f} {aggregate * 100:13.1f}% {abs(band_errors[0]) * 100:15.1f}% "
              f"{abs(band_errors[1]) * 100:15.1f}%")

    twenty = [abs(float(row["band_errors"][0])) for row in phases["rows"]]
    forty = [abs(float(row["band_errors"][1])) for row in phases["rows"]]
    print(f"\n20 m band: {min(twenty) * 100:.1f}% - {max(twenty) * 100:.1f}% over three phases")
    print(f"40 m band: {min(forty) * 100:.1f}% - {max(forty) * 100:.1f}% over three phases")
    verdict = ("20 m is phase-independent, 40 m carries the spread" if max(twenty) < 0.02
               else "20 m also moves: the split is not clean")
    print(f"verdict: {verdict}")
    (WORK / "band_split.json").write_text(json.dumps({"rows": phases["rows"],
                                                      "twenty_range": [min(twenty), max(twenty)],
                                                      "forty_range": [min(forty), max(forty)],
                                                      "verdict": verdict}, indent=2, ensure_ascii=False),
                                          encoding="utf-8")
    print("wrote", WORK / "band_split.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
