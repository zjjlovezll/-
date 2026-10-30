# Three estimators for one bump, and why one pass cannot give its amplitude (M5, step 3)

Date: 2026-10-31. Script: [`../scripts/s114_parametric_split.py`](../scripts/s114_parametric_split.py).
Report: [`../reports/load_split_inversion_2026-10-31/parametric.json`](../reports/load_split_inversion_2026-10-31/parametric.json).
Previous step: [LOAD_SPLIT_INVERSION_2026-10-31.md](LOAD_SPLIT_INVERSION_2026-10-31.md).

Round 251 inverted the bump through a table fitted on one amplitude and failed out of range, because
the table ends where that amplitude's gap ended. This round tests two further estimators against the
same three known bumps and the same pre-registered gates, and the result is not "one of them is
better": all three fail out of range for reasons that turn out to be the same reason.

## 1. The three estimators

| # | estimator | free parameters | calibrated on |
|---|---|---|---|
| T | monotone table `sigma(u)`, 40 quantile bins (round 251) | 40 bins | one run (50 µm) |
| P | `sigma = 0.5(1 − tanh((u − u0)/w))`, inverted in closed form | 2 | two runs, one held out |
| S | zero-parameter: station where `sigma` crosses 0.5, then `z = d(s*)` | 0 | none |

`u = d(s) − z(s)` is the gap the contact sees, `d` the pristine crown gap from the case geometry.

## 2. Measured

Leave-one-out for P (each amplitude held out once); T and S use their own protocol.

**T — table, calibrated on 50 µm only**

| held out | peak true | peak est | p95 | at s |
|---|---|---|---|---|
| 50 (in range) | 50.0 | 56.8 | **15.0 µm** | 58.36 (0.14 m) |
| 100 | 100.0 | 76.5 | 49.0 | 58.24 |
| 200 | 200.0 | 101.7 | 147.5 | 57.98 |

**P — two-parameter tanh, leave-one-out**

| calibration | u0 | w | held out | peak true | peak est | p95 | at s | gates |
|---|---|---|---|---|---|---|---|---|
| 100 + 200 | −10.73 µm | 80.4 µm | 50 | 50.0 | **127.6** | 66.4 | 58.51 | n/n/Y |
| 50 + 200 | −10.41 | 68.9 | 100 | 100.0 | **217.5** | 34.1 | 58.71 | n/n/n |
| 50 + 100 | −15.24 | 44.4 | 200 | 200.0 | **227.1** | 86.6 | 58.02 | n/n/n |

The parametrisation extends past its samples, but it inverts badly near saturation: `σ → 1` sends
`arctanh(1 − 2σ) → −∞`, so a frame at `σ = 0.99` reports an enormous bump. Extrapolating the *model*
fixed the clamping but replaced it with amplification.

**S — zero-parameter transfer station**

| amplitude | s\* | z = d(s\*) | truth at s\* | error |
|---|---|---|---|---|
| 50 | 58.211 m | 21.2 µm | 48.6 | **−27.4** |
| 100 | 58.044 | 36.9 | 93.0 | **−56.1** |
| 200 | 57.789 | 60.4 | 167.8 | **−107.4** |

## 3. The one number that explains all three failures

Estimator S assumes the blade takes half the load when the gap is zero. The measured gap at the
crossing says otherwise, and it **moves with amplitude**:

```
50 um   u(s*) = d - z = 21.2 - 48.6 = -27.4 um
100 um                = 36.9 - 93.0 = -56.1 um
200 um                = 60.4 - 167.8 = -107.4 um
```

So the half-load gap is not a constant of the contact geometry — it is a function of how much of the
stock's load has already been given up (round 250: the stock's zero-force frames in the crossing window
go 0 / 37 / 161 for the same three amplitudes). The split is therefore **not a function of the gap
alone**; any estimator of the form `σ = f(u)` — table or tanh — is mis-specified as soon as the bump
gets big enough to unload the stock.

## 4. Consequences for M5/M7 (recorded, not glossed)

1. **A single pass cannot give the peak amplitude.** It gives the station where the transfer happens —
   and even that only via a model, because the gap at which the transfer happens depends on the branch.
   Estimator S's error is not noise; it is the branch.
2. **The amplitude needs the forward model inside the inversion**, not a lookup: solve for `z(s)` with
   the contact/load transfer in the loop (M7), so the stock-unloading branch is represented instead of
   being fitted by a one-dimensional map.
3. **The ensemble is mandatory, as M4's arithmetic already said.** Three distinct lateral offsets are
   needed for a surface claim; the same arithmetic now also explains the amplitude: one pass provides
   one transfer-station equation per axle, and the branch it lands on is set by how much of the stock
   is still carrying.

What *does* work, and is worth keeping: localisation. Every estimator placed the feature within
0.52 m, the table placed the 50 µm peak at 0.14 m, and in range the table recovers the profile to
p95 15.1 µm (0.23 × the static penetration).

## 5. Boundaries

One speed (80 km/h), one centre (58.5 m), one σ (1.2 m), three amplitudes, blade body only, straight
route. Gates unchanged from the task book; none was relaxed after the numbers came in.

## 6. Recompute

```bash
cd Velch
export PYTHONPATH=src
python -X utf8 scripts/s113_profile_inversion.py     # estimator T
python -X utf8 scripts/s114_parametric_split.py      # estimators P and S
python -X utf8 -m pytest tests/test_load_split_inversion.py tests/test_parametric_split.py -q
```
