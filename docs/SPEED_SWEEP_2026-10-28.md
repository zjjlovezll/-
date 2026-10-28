# Five drawn speeds: the straight-route amplitude claim is one band wide, not six-of-eight

Round 11 of the current goal. Round 194 reported **6 of 8** band amplitudes inside 2 dB at **70.32 km/h**.
That is a point, not a capability: gate 6 asks for inversion "under realistic random speed". This round
repeats the entire round-194 protocol at **five speeds drawn from a seed** and reports how many reach the bar.

The answer is **0 of 5**, and the per-band column explains why it is not a uniform failure.

## 1. Protocol — identical to round 194, nothing re-tuned

* four log-spaced bands over 0.10–0.30 m: **0.1000–0.1316 / 0.1316–0.1732 / 0.1732–0.2280 / 0.2280–0.3000 m**;
* each band a sum of 24 harmonics, uniform wavenumbers, random phases, normalised to 8 µm rms;
* calibration seed **20261029** excites one band at a time; test seeds **20261030 / 20261031** sum all four;
* same channel (`axle1_z_acc_m_per_s2`), same patch 42.5–45.5 m, same 2.5 mm step, same 50 mm fades, left rail;
* truth = **that record's own band rms** (the primary definition fixed in round 194), criterion 2 dB.

Two differences, both fixed before the runs:

1. the speeds are **drawn**, `default_rng(20261032).uniform(70, 90, 5)`, so the set cannot be chosen after
   seeing which speeds behave;
2. a speed counts as **quantifiable only at ≥ 7 of its 8 predictions**, one above round 194's own count — the
   bar is raised, not lowered, because a draw that merely reproduces "6/8" would prove nothing.

The implementation calls round 194's own estimator (`s38_spectral_bands.main`) with the module's speed
constant patched, so the calibration, the window and the projection cannot drift between the two rounds.
Verified before the sweep that the patch reaches the case (`travel_speed_m_s = 22.222` at 80 km/h) and the
window (0.1125–0.2475 s at 80 km/h vs 0.1280–0.2816 s at 70.3206 km/h).

## 2. Result

| drawn speed | spectral hits | scalar hits | quantifiable |
|---|---|---|---|
| 78.68 km/h | 5/8 | 6/8 | no |
| 79.47 | 6/8 | 6/8 | no |
| 82.16 | 6/8 | 6/8 | no |
| 88.02 | 6/8 | 3/8 | no |
| 88.16 | 6/8 | 3/8 | no |

```
quantifiable speeds: 0/5        total hits: 29/40 (72.5 %)
```

## 3. The failure is one band wide — the widest band is the robust one

Hits per band across the ten predictions (five speeds × two seeds):

| band (m) | hits |
|---|---|
| 0.1000–0.1316 | 8/10 |
| 0.1316–0.1732 | **6/10** |
| 0.1732–0.2280 | **5/10** |
| 0.2280–0.3000 | **10/10** |

Per-prediction errors (dB, seed 1030 then 1031, bands in the order above):

| speed | b0 | b1 | b2 | b3 | b0 | b1 | b2 | b3 |
|---|---|---|---|---|---|---|---|---|
| 78.68 | −0.13 | +2.04 | +2.15 | +1.19 | +2.31 | +1.84 | +0.58 | +1.76 |
| 79.47 | +1.00 | +1.77 | **+2.62** | +1.27 | **+2.45** | +1.87 | +0.41 | +1.75 |
| 82.16 | +0.38 | +0.65 | **+2.82** | +1.41 | +1.47 | **+2.07** | −0.23 | +1.36 |
| 88.02 | +0.76 | +0.50 | **+2.66** | +1.72 | +0.31 | **+2.53** | −0.99 | +1.78 |
| 88.16 | +1.10 | +0.53 | **+2.68** | +1.71 | +0.31 | **+2.52** | −1.00 | +1.77 |

Two things are visible that the hit count alone hides:

1. **The misses are all positive, +2.0 to +2.8 dB**, and they sit in the two middle bands (0.132–0.228 m).
   The estimator **over-recovers** those bands at speed; it does not lose them.
2. **0.2280–0.3000 m is 10/10 at every drawn speed**, all ten inside +1.19 to +1.78 dB. That is the one band
   whose ±2 dB claim survives the sweep.

## 4. Reading, and the one thing this retracts

Round 194's "6/8 at 70.32 km/h" was the **best case**, not the typical one: at the five drawn speeds the
spectral estimator reached 6/8 four times and 5/8 once, never 7/8. The honest capability statement for the
straight route is therefore **per band, per speed**:

> At 70–90 km/h, the 0.228–0.300 m band is quantifiable (±2 dB) at every speed tested; the 0.100–0.132 m band
> at all but one speed-seed pair; the 0.132–0.228 m bands are **not** quantifiable at any drawn speed, with a
> systematic **+2 to +2.8 dB over-recovery**.

A single "6/8 within ±2 dB" number must not be quoted again without its band breakdown, because the same
protocol gives 0/5 speeds by the raised bar and 10/10 on one band.

The scalar estimator is worse at the top of the range (3/8 at 88 km/h vs 6/8 spectral) and once better
(6/8 vs 5/8 at 78.68 km/h); it is not a substitute for the frequency-resolved route, but at one speed it beat
it, which is recorded rather than smoothed over.

## 5. Why the mid bands over-recover at speed — one hypothesis falsified, one open

The obvious candidate was **fewer frequency bins in the analysis window**: the window is the time the leading
axle spends over the 3 m patch, **0.2816 s at 70.32 km/h** against **0.2045 s at 88.16 km/h**, so a coarser
FFT and less averaging. **The measurement falsifies it**: the bins kept are

| band | bins at 70.32 km/h (round 194) | bins at 88.16 km/h (this round) |
|---|---|---|
| 0.1000–0.1316 | 7 | 7 |
| 0.1316–0.1732 | 5 | 5 |
| 0.1732–0.2280 | 4 | 4 |
| 0.2280–0.3000 | 3 | 4 |

The count is essentially unchanged because the estimator's band edges are converted to Hz with the *local*
speed: at higher speed the band is wider in Hz (∝ v) while the window is shorter (∝ 1/v), and the product —
the number of bins — stays put. So "coarser grid" is not the mechanism, and it is recorded as refuted rather
than dropped.

What remains is that **the same spatial band is interrogated at a different frequency range**: 0.1732–0.2280 m
is 379–483 Hz at 70.32 km/h and 477–608 Hz at 88.16 km/h. Round 192 measured at *fixed* speed that the
single-tone operator is **not flat inside a band** (a 29 % gain rise across an 85.19 → 94.23 Hz step), so a
same-class calibration at one speed cannot be carried to another while the band's frequency span moves. Two
candidates survive this round — the in-band transfer slope interacting with each record's spectral shape, and
each record's own rms/crest factor — and **this round did not separate them**. Separating them needs a longer
patch at fixed speed (longer window, same class), which is the next experiment, not a claim.

## 6. Two limits of this sweep, stated plainly

1. **Two of the five draws landed almost on top of each other** (88.02 and 88.16 km/h; six of their eight
   predictions agree to within 0.03 dB). The effective number of distinct speeds is therefore **four**, and
   the per-band counts of ten predictions are not ten independent ones.
2. **The draw stayed in the upper half of the declared range** (78.68–88.16 of 70–90). Nothing here says what
   happens at 70–78 km/h beyond round 194's single point, and nothing says what happens above 90 km/h, where
   the pipeline would be extrapolating and gate 5 forbids it.

## 7. What this changes for gate 6

* the straight half of gate 6 is now measured at five drawn speeds and **degrades explicitly**: detection and
  the widest band's amplitude stand; the two middle bands are not quantifiable at any drawn speed;
* the artefact `reports/inversion_synthetic_2026-10-28/speed_sweep.json` holds every per-prediction number and
  the pre-registered criterion, so the band breakdown can be re-derived without re-running anything;
* `measurement_validation_status` is unchanged (`not_evaluated`): this is still a synthetic route and claims
  nothing about a measurement.

## 8. Recompute

```
cd F:\ai道岔状态反演辨识\Velch
PYTHONPATH=src python -X utf8 scripts/s42_speed_sweep.py     # ~15 min, 30 runs, writes speed_sweep.json
PYTHONPATH=src python -X utf8 -m pytest tests/test_speed_sweep.py -q
```
