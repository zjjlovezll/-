# The forward operator's answer to a known surface bump (M5, step 1)

Date: 2026-10-31. Script: [`../scripts/s112_surface_sensitivity.py`](../scripts/s112_surface_sensitivity.py).
Report: [`../reports/surface_sensitivity_2026-10-31/sensitivity.json`](../reports/surface_sensitivity_2026-10-31/sensitivity.json).

M5 asks whether the *measured* surface can be compared with the section surface point by point. That
comparison is only meaningful if the forward operator has a measured gain: put a known bump on the
surface, and see how — and where — the response answers. This document records that gain, the three
checks it has to pass, and the one it does not pass.

## 1. What was perturbed, and why that body

A Gaussian bump was added to `profile.z_offset_m` on the **blade** body's stations:

```
centre 58.5 m   sigma 1.2 m   peak 50 / 100 / 200 um
```

The blade's station table is 0.193 m apart and can represent a 1 m feature. The stock body's table is
13 m apart and cannot — a bump written there would be smoothed into nothing by the interpolation
between stations, and the test would measure the station spacing rather than the contact. This is a
practical limitation, not a physical one: the stock geometry in the canonical case is the same section
everywhere, which is exactly why the blade is the body under test here.

Four runs, 0.60 s at 80 km/h, 1201 frames each, all seven gates 7/7:

| run | case sha | wall |
|---|---|---|
| baseline (no bump) | `55d6fd49` | 365.1 s |
| bump 50 µm | `20295a3d` | 366.2 s |
| bump 100 µm | `cad4db6b` | 397.2 s |
| bump 200 µm | `28051835` | 422.5 s |

The observation channel is the **axle box**, not the wheelset: this vehicle carries one box body per
side (`axle1_box_right_z_acc_m_per_s2` / `axle1_box_left_z_acc_m_per_s2`), so the left/right comparison
is available without any inference. Body loads come from `body_normal_force_n` with
`meta["body_labels"]` (`axle1_right/stock`, `axle1_right/blade`).

## 2. Measured

Baseline `|a_z|` on the right box: max **2.206 m/s²**, median 0.021 m/s². The solver is deterministic —
a repeat run is bit-identical — so there is no stochastic floor to clear; the meaningful question is
whether the response is visible against the baseline's own motion, and it is.

| amplitude µm | peak \|Δa\| m/s² | at s (m) | rms in window | rms gain (m/s²)/µm | peak gain (m/s²)/µm | L/R | stock zero frames | blade max |
|---|---|---|---|---|---|---|---|---|
| 50 | 0.6367 | 58.54 | 0.2333 | 0.00467 | **0.01273** | 0.183 | **0 / 314** | 59.5 kN |
| 100 | 1.8586 | 59.13 | 0.5928 | 0.00593 | **0.01859** | 0.144 | **37 / 314** | 61.5 kN |
| 200 | 1.8470 | 59.50 | 0.6212 | 0.00311 | **0.00924** | 0.161 | **161 / 314** | 62.1 kN |

## 3. The three checks

| check | result | evidence |
|---|---|---|
| non-zero (visible) | **PASS** | response is 29 %, 84 %, 84 % of the baseline's own peak |
| localised to the bumped rail | **PASS** | left/right = 0.183 / 0.144 / 0.161 (the left rail has no bump) |
| localised in station | **PASS** | peak at 58.54 / 59.13 / 59.50 m, all within **1.0 m** of the centre |
| monotone in amplitude | **FAIL** | gain 0.01273 → 0.01859 → 0.00924 (spread **2.01**) |

## 4. Why it is not monotone — the branch switch

The stock body's force in the crossing window (57–60.5 m, 314 frames) says it directly:

```
50 um   stock min  0.4 kN   zero frames   0/314   blade max 59.5 kN
100 um  stock min  0.0 kN   zero frames  37/314   blade max 61.5 kN
200 um  stock min  0.0 kN   zero frames 161/314   blade max 62.1 kN
```

The static penetration here is **63.70 µm**. A bump of 50 µm leaves the wheel on both bodies nearly all
the time and the load merely shifts; a bump of 100 µm or more lifts the wheel **off the stock** for a
growing part of the crossing, and the blade alone carries it. Past that point the response no longer
grows with the bump — the geometry transition is what the axle box feels, and it is the same transition
whatever the amplitude above the threshold.

So the linear regime ends at roughly **0.8 × the static penetration**, i.e. around 50 µm.

## 5. What this means for the inversion

1. **Acceleration is a localiser, not an amplitude carrier, in this range.** It says which rail and
   which station to within ~1 m, and it does so at 3–5× the other rail's response. It does not carry a
   linear amplitude once the bump approaches the penetration.
2. **The per-body load split is the amplitude carrier.** The same runs show the branch unambiguously:
   stock zero frames 0 → 37 → 161, blade maximum 59.5 → 61.5 → 62.1 kN. That is a monotone, discrete,
   easily measured signal, and it is the same observable that already read the 67.8 % load transfer at
   59.73 m in the 0.40 s run.
3. **The M7 inversion must therefore be built on the load split as the primary observable**, with
   acceleration used for localisation and for the small-amplitude (random roughness, corrugation)
   regime where the operator is linear. Claiming an amplitude from acceleration alone across the whole
   range would be reading a branch switch as a gain.

## 6. Boundaries

- One speed (80 km/h), one station (58.5 m), one sigma (1.2 m), three amplitudes, one body (blade),
  straight route, rigid wheelset in this case's sense (the wheelset is the axle-box model's, the rail
  is flexible).
- The bump is applied through `z_offset_m`, which shifts the whole section vertically; it does not
  change the blade's cross-section shape. That is the same approximation the canonical case already
  uses, and is registered as such.
- "Peak \|Δa\|" is a single frame; the rms in the window is reported beside it precisely because the
  peak is the noisier statistic (rms spread 1.9 vs peak spread 2.0 — both non-monotone, so the
  conclusion does not hinge on the choice).

## 7. Recompute

```bash
cd Velch
export PYTHONPATH=src
python -X utf8 scripts/s112_surface_sensitivity.py --build
python -X utf8 scripts/s99_run_archive.py --case vehicles/turnouts/CN60-1100-1_18/cases/straight_one_set.json \
    --speed-kmh 80 --duration 0.6 --note campaign=surface-sensitivity-baseline
for amp in 050.0 100.0 200.0; do
  python -X utf8 scripts/s99_run_archive.py --case "F:/ai道岔状态反演辨识/scratch/s112/one_set_bump${amp}um.json" \
      --speed-kmh 80 --duration 0.6 --note campaign=surface-sensitivity
done
python -X utf8 scripts/s112_surface_sensitivity.py --analyze
python -X utf8 -m pytest tests/test_surface_sensitivity.py -q
```

The four runs cost about 26 minutes of wall clock in total.
