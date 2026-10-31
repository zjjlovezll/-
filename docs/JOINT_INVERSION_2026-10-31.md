# M7 step 2: joint forward fit — 2 parameters instead of 25

Round 261.  Round 260 inverted the split law station by station and failed (0/3 amplitudes, best
p95 98.1 µm against a 22 µm gate).  Its own error budget said why: pointwise inversion multiplies the
law's error (~30 µm in `u`) and the per-station share flicker (~50 µm) by the ramp's geometry, and
leaves a 43 µm background even after the null run defines the zero.

This round keeps the observables and the law but never inverts it pointwise.  It fits **two**
parameters — amplitude `A` and centre `s0` — by matching the *predicted* share to the measured one:

```
z(s)     = A · exp(-0.5·((s - s0)/1.2 m)²)        width is a declared prior
sigma(s) = law(u0(s) + z(s), g0(w(s)))            u0 from the un-bumped run, law from s118
```

Two parameters against ~25 stations of a curve with a 0.37 swing is well conditioned; the pointwise
version had ~25 parameters against the same data.

## 1. Method decisions (all three change the number)

1. **The null run supplies the operating state.**  `u0(s)` is obtained by inverting the law on the
   un-bumped run, where the answer must be "no bump".  The law is never trusted absolutely — that is
   what removes the 43–105 µm bias round 260 measured.
2. **The bump adds to that state (plus, not minus).**  Measured at 58.5 m: the un-bumped run sits at
   share 0.586 and the 50 µm bump at 0.954, i.e. a raised blade takes *more* load.  The first version
   of this fit used minus and predicted 0.210 where the run showed 0.954 — it collapsed onto its
   bounds and reported "0/9".
3. **The width is a prior, declared.**  `sigma_s = 1.2 m` is the shape the runs were built with, and
   round 258 already showed the onset station does not track the bump's width.  Nothing here claims
   to measure the width.

## 2. Result (gates identical to round 260, declared before this script existed)

```
  truth   fit A   rel %   centre  d centre   p95 um  worst 2mm %  peak err m  G-ABS  G-REL  G-LOC
   20.0    21.4    0.28   58.493    -0.007     1.41         0.28       0.011   PASS   PASS   PASS
   30.0    32.1    0.41   58.499    -0.001     2.05         0.41       0.000   PASS   PASS   PASS
   40.0    43.3    0.66   58.479    -0.021     3.38         0.68       0.022   PASS   PASS   PASS
   50.0    62.7    2.53   57.916    -0.584    24.42         4.93       0.589   FAIL   FAIL   FAIL
   60.0    66.1    1.23   58.464    -0.036     6.38         1.28       0.033   PASS   PASS   PASS
   80.0    87.6    1.52   58.524     0.024     7.72         1.55       0.022   PASS   PASS   PASS
  100.0   221.6   24.32   57.426    -1.074   161.66        32.58       1.078   FAIL   FAIL   FAIL
  120.0   235.9   23.18   58.541     0.041   115.36        23.21       0.044   FAIL   FAIL   PASS
  200.0   400.0   40.00   57.411    -1.089   283.51        57.18       1.089   FAIL   FAIL   FAIL
5/9 pass all three gates (single start at the nominal centre)
4/9 pass (multi-start over centre)
```

For the five passing amplitudes the amplitude is recovered to **0.28–1.52 %** and the profile to
**p95 1.4–7.7 µm** — inside the 22 µm gate by 3–15×, and the position to **0.000–0.033 m**, inside
the 0.20 m gate by 6–∞.  That is the first time this project has an end-to-end surface reconstruction
that clears the pre-registered absolute gate.

## 3. What still fails, and why

1. **≥100 µm is not identifiable from the share alone.**  The share reaches 1.000 on those runs, so
   `A` and `s0` stop being separately determined; the fit runs to its amplitude bound (400 µm) and the
   residual blows up.  The observable that does carry those amplitudes is the **onset station**
   (round 257: 3.3 mm/µm, 1.4–4.7 µm per frame) — but that table was calibrated on these very runs, so
   quoting it as a recovery here would be fitting the calibration set.  It needs a hold-out amplitude
   (e.g. 150 µm, or a different centre) before it can be reported as an independent measurement.
2. **50 µm lands in a shifted minimum** (centre −0.584 m, A 25 % high, p95 24.4 µm).  Multi-start does
   not rescue it — it finds the same minimum — so the share curve genuinely prefers this solution at
   that amplitude.  Honest reading: between 40 and 60 µm the two parameters trade off.
3. **Multi-start lowers the cost but raises the error** on 80 µm (87.6 → 141.9 µm, cost lower): the
   model is misspecified somewhere, and a lower residual is not a better answer.  Both modes are
   reported for that reason, not just the flattering one.

## 4. Boundary of the law

The measured `u` window is finite; outside it the interpolation clamps (`left=1.0`, `right=0.0`).
At a 400 µm raise the forward map therefore returns share 0 — an artefact, pinned by a test.  Fits
that push the state past the window are extrapolation and are reported as failures, not as numbers.

## 5. Boundaries of the claim

* One speed (80 km/h), one bump width (1.2 m prior), one centre (58.5 m), one side, one pass.
* The truth is synthetic: this is an estimator test (class B), not a measurement of a real rail.
* Coverage is unchanged: one pass sees 4 mm of the 37.15 mm head (11 %); nine passes are the design.
* The share is filtered with a 1.2 m median window chosen on the null run (round 260), which is wider
  than the feature's own 1.2 m sigma — the estimator is trading resolution for background on purpose.

## 6. Reproduce

```bash
PYTHONIOENCODING=utf-8 python -X utf8 scripts/s124_joint_inversion.py
python -X utf8 -m pytest tests/test_joint_inversion.py -q
```
