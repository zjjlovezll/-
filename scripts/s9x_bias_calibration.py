"""Is the band bias a *constant* we can calibrate, or just this draw again?

`docs/BAND_CAPABILITY_2026-10-26.md` §12 found two bands (0.05-0.1 m and
0.8-1.6 m) that come back 15-21 % low in all three seeds with a 1.3-6.7 %
spread - i.e. bias, not scatter.  A bias is only worth calibrating if it is
constant out of sample, so this script fits one multiplicative constant per band
on the FIRST TWO seeds and then applies it to the THIRD seed, which was never
used in the fit.  Reporting both halves is the point: an in-sample improvement
would prove nothing.

Run:  python -X utf8 scripts/s9x_bias_calibration.py
"""

from __future__ import annotations

import json
import math
import pathlib
import sys

import numpy as np

WORK = pathlib.Path(r"F:\velch_tmp\s9u")


def main() -> int:
    state = json.loads((WORK / "seed_spread.json").read_text(encoding="utf-8"))
    rows = state["rows"]
    names = [row["band"] for row in rows]
    truth = np.array([row["truth_um"] for row in rows], dtype=float)
    values = np.array([[float(value) for value in row["positive_um"]] for row in rows], dtype=float)

    fit = 0.5 * (values[:, 0] + values[:, 1])
    held = values[:, 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        scale = np.where(fit > 0, truth / fit, 1.0)
        corrected = held * scale
        db_held = np.full(len(rows), np.nan)
        db_corrected = np.full(len(rows), np.nan)
        for index in range(len(rows)):
            if truth[index] > 0 and held[index] > 0:
                db_held[index] = 20.0 * math.log10(held[index] / truth[index])
            if truth[index] > 0 and corrected[index] > 0:
                db_corrected[index] = 20.0 * math.log10(corrected[index] / truth[index])

    print(f"{'band':>10} {'truth':>7} {'fit12':>8} {'scale':>7} {'held3':>8} {'dB before':>10} {'after':>8}")
    for index, name in enumerate(names):
        print(f"{name:>10} {truth[index]:7.3f} {fit[index]:8.3f} {scale[index]:7.3f} "
              f"{held[index]:8.3f} {db_held[index]:10.2f} {db_corrected[index]:8.2f}")

    usable = [index for index in range(len(rows)) if truth[index] >= 8.0]
    before = sum(1 for index in usable if abs(db_held[index]) <= 2.0)
    after = sum(1 for index in usable if abs(db_corrected[index]) <= 2.0)
    print(f"\nbands with truth >= 8 um: {len(usable)}")
    print(f"  within 2 dB on the held-out seed, uncalibrated: {before}/{len(usable)}")
    print(f"  within 2 dB on the held-out seed, one constant per band fitted on two other seeds: "
          f"{after}/{len(usable)}")
    for index in usable:
        print(f"    {names[index]:>10}: {db_held[index]:+6.2f} dB -> {db_corrected[index]:+6.2f} dB"
              f"  (scale {scale[index]:.3f})")

    state["calibration"] = {"scale": scale.tolist(), "bands": names,
                            "held_out_seed": state["seeds"][2],
                            "db_before": db_held.tolist(), "db_after": db_corrected.tolist()}
    (WORK / "bias_calibration.json").write_text(json.dumps(state["calibration"], indent=2, ensure_ascii=False),
                                                encoding="utf-8")
    print("wrote", WORK / "bias_calibration.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
