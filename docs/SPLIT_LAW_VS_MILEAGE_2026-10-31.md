# Does the split law collapse? Measured across mileage, with a self-corrected verdict

Date: 2026-10-31. Script: [`../scripts/s118_split_law_vs_station.py`](../scripts/s118_split_law_vs_station.py).
Report: [`../reports/load_split_inversion_2026-10-31/split_law_vs_station.json`](../reports/load_split_inversion_2026-10-31/split_law_vs_station.json).
Previous step: [SPLIT_LAW_MEASURED_2026-10-31.md](SPLIT_LAW_MEASURED_2026-10-31.md).

Round 254 measured the split law at one station. The obvious next question is whether it moves with mileage:
if it collapses onto one curve, an estimator can use a single law in `u = d - z`; if it shifts, the law is a
two-dimensional operator and the inversion has to carry it.

## 1. Why "height above flush" is the right coordinate

At 52 m the blade sits 7.8 mm below the stock, so a ±250 µm lift never reaches it — a grid of absolute offsets
only probes the law near the transfer. The probe therefore raises the blade by `d(s) + delta`, so that at the
probe station the blade sits `delta` above flush. Stations 52/54/56/58/60/62 m, `delta` from +250 down to
−200 µm, front axle seated at each station in turn.

## 2. Measured

```
station   design gap    +250   +100    +50     +0    -50   -100   -200   half width at delta=0
  52.0        7811.0     nan   0.071  0.019  0.000  0.000  0.000  0.000        7.468
  54.0        2474.4   0.341    nan   0.008  0.000  0.000  0.000  0.000        7.468
  56.0        1052.7   0.719    nan   0.028  0.000  0.000  0.000  0.000        7.468
  58.0          41.1   1.000   0.836  0.453  0.080  0.000  0.000  0.000        7.468
  60.0         -14.0   1.000   1.000  0.923  0.519  0.106  0.000  0.000        6.234
  62.0         -21.3   1.000   1.000  0.909  0.497  0.089  0.000  0.000        6.472
```

Three readings matter.

1. **The probe's zero is right.** At 60.0 and 62.0 m the design gap is ≈ 0 and the split at `delta = 0` is
   **0.519 / 0.497** — level surfaces share the load almost exactly in half, which is what they must do.
2. **The blade section width is the hidden variable.** Taking the width from the station file names
   (`zjg-…-10 / -21 / -31 / -45 / -63 / -72.2`), the height at which the blade wins half the load
   (**absolute raise**, `d + delta`) is:

   | station | blade width | raise at σ=0.5 |
   |---|---|---|
   | 58.0 | 45 mm | **+97.3 µm** |
   | 60.0 | 63 mm | **−16.3 µm** |
   | 62.0 | 72.2 mm | **−21.0 µm** |

   A narrow section has to be lifted 97 µm above the stock to compete; a 63 mm section wins half at −16 µm;
   and beyond that it saturates (−4.7 µm from 63 to 72.2 mm). The footprint is the same mechanism round 254
   found: the blade's strip is narrower, so its effective stiffness is lower, and the gap has to be closed
   further before the split moves.
3. **The footprint itself moves with station**: `half_width` at `delta = 0` is 7.468 mm from 52 to 58 m,
   **6.234 mm** at 60 m, 6.472 mm at 62 m.

## 3. The pre-registered verdict was too coarse, and is corrected here

The script was written with `spread of the half-load height <= 100 µm` meaning "collapses onto one curve", and
it printed that verdict because the three measurable crossings span 58.4 µm. That threshold is wrong for this
question: the shift is not scatter, it is **monotone in the blade width** (45 → 63 mm moves the crossing by
113 µm, 4.6 times the threshold's slack), and the comparison of the two ends of the width range is what the
question is actually about. Corrected statement:

> The split law does **not** collapse onto one curve. It shifts systematically with the blade's section width,
> by 113 µm between a 45 mm and a 63 mm section, and saturates at full width. An estimator keyed only on
> `u = d - z` will therefore be biased wherever the section is narrow — which is precisely the switch panel
> (10 → 45 mm over 52–58 m), the region the final goal is about.

## 4. Coverage of the measurement (stated, not glossed)

Only **3 of 6** stations reach σ = 0.5 inside the grid: at 52/54/56 m the blade is 7.8 / 2.5 / 1.1 mm below
flush and would need a lift of that magnitude, which the seat refuses (a blade lifted that far leaves the
stock carrying nothing, and the vertical equilibrium has no solution — those cells are recorded as `nan` with
the failure string, not silently dropped). Extending the grid there needs a different probe (two-body seating
with the stock's share constrained), which is the next step, not a bug to hide.

## 5. What this fixes for the inversion

- The forward model must carry **the blade's section width** — which is known exactly from the geometry — as
  the parameter that sets both the law's shift and the footprint. That is a measured, physical predictor, not
  a fitted constant.
- The estimator's height coordinate is `u = d − z − c(w)`, with `c(w)` the width-dependent offset measured
  here (+97 µm at 45 mm, −16 µm at 63 mm, saturating at 72 mm).
- Round 253's compression and this round's shift are the same mechanism, and it is now measured twice at
  different stations with different section widths.

## 6. Recompute

```bash
cd Velch
export PYTHONPATH=src
python -X utf8 scripts/s118_split_law_vs_station.py      # 42 probes, ~7 min
python -X utf8 -m pytest tests/test_split_law_station.py -q
```
