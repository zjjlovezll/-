# The saturation-onset station: an amplitude carrier that survives the split's knee

2026-10-31 · round 257 · case `turnout_cn60_1100_straight_one_set` · 80 km/h · one pass · blade bump at 58.5 m

## 1. Why this observable

Round 256 left one number alive above the knee of the load split.  The split saturates: a 100 µm bump and a
200 µm bump both read about 62 µm of gap closure, because once the gap is past roughly −50 µm the blade owns the
whole wheel and `σ → 1`.  What still moved was *where saturation starts* — 57.98, 57.81, 57.58 m in the peak
station of those three runs.

Three points are not a calibration, and the peak station is a poor estimator because the split sits on a plateau
there and the argmax wanders inside it.  So this round (a) defines the onset on the **rising flank** and (b)
measures it over six more amplitudes, chosen to straddle the knee.

## 2. Definition, fixed before the runs

```
onset(s)  =  the first station at which the smoothed blade share reaches 0.95
smoothing =  median filter over 0.20 m (the same window s113 uses)
share     =  blade / (stock + blade) per output frame, masked where the total is under 1 kN
```

Pre-registered gates, written into `scripts/s120_onset_resolution.py` before the campaign existed:

1. `onset` never decreases as the amplitude grows;
2. adjacent amplitudes differ by at least one output interval — 80 km/h with 5e-4 s spacing gives **11.11 mm**;
3. the run from 20 µm to 120 µm does not collapse onto one value;
4. a campaign that does plateau is reported as *not resolving*, not as a pass.

## 3. The archived amplitudes, re-read with the new definition

| amplitude | onset | peak station | share max | run |
|---|---|---|---|---|
| 50 µm | **58.500 m** | 58.511 | 0.959 | `one_set_bump050.0um-…-20295a3d` |
| 100 µm | **58.256 m** | 58.300 | 1.000 | `one_set_bump100.0um-…-cad4db6b` |
| 200 µm | **57.989 m** | 58.033 | 1.000 | `one_set_bump200.0um-…-28051835` |

Note that these are **not** the peak stations quoted in round 256 (57.98 / 57.81 / 57.58).  The crossing sits
0.01–0.06 m later than the argmax, and the argmax is the noisier of the two — at 50 µm the crossing is even
*earlier* than the argmax by one frame, because the median filter has already pulled the flank up while the
plateau is still flat.  Both are reported; the crossing is the one this round uses.

## 4. The campaign: 20–120 µm, six new runs

`scripts/s120_onset_resolution.py --build` writes one case per amplitude, a Gaussian on the blade stations only
(161 of them, centre 58.5 m, σ 1.2 m), everything else inherited from the canonical one-set case including the
4× wheel and `seat_lateral`.  Six runs at 80 km/h for 0.60 s, 1201 frames each, seven gates 7/7 each.

| amplitude | onset | peak station | share max | gate 2 |
|---|---|---|---|---|
| 20 µm | **never saturates** | — | < 0.95 | — |
| 30 µm | **never saturates** | — | < 0.95 | — |
| 40 µm | **never saturates** | — | < 0.95 | — |
| 50 µm | 58.500 m | 58.511 | 0.959 | — |
| 60 µm | **58.422 m** | 58.511 | 0.995 | 7 frames |
| 80 µm | **58.322 m** | 58.367 | 1.000 | 9 frames |
| 100 µm | 58.256 m | 58.300 | 1.000 | 6 frames |
| 120 µm | **58.178 m** | 58.233 | 1.000 | 7 frames |
| 200 µm | 57.989 m | 58.033 | 1.000 | 17 frames |

```
onset monotone (never later)   PASS
onset resolvable (>=1 frame)   PASS
collapsed onto one station     no
VERDICT: the station carries the amplitude at this resolution
```

## 5. What the station buys, in numbers

Linear fit over the six resolvable amplitudes:

```
onset = 58.610 m − 3.270 mm per um × amplitude        max residual 53 mm (about 5 frames)
```

so one output frame (11.11 mm) is worth **3.4 µm of amplitude** on average, and the local slope runs from
**7.8 mm/µm** at the 50–60 µm end to **2.4 mm/µm** at the 120–200 µm end.  In amplitude terms:

| amplitude interval | step | per-frame amplitude resolution |
|---|---|---|
| 50 → 60 µm | 78 mm (7 frames) | **1.4 µm** |
| 60 → 80 µm | 100 mm (9 frames) | 2.2 µm |
| 80 → 100 µm | 67 mm (6 frames) | 3.3 µm |
| 100 → 120 µm | 78 mm (7 frames) | 2.9 µm |
| 120 → 200 µm | 189 mm (17 frames) | **4.7 µm** |

That is **5–16× finer than the 22 µm absolute gate** of the taskbook, and it is finer than anything the split
itself can deliver above the knee.  It is the first amplitude observable in this work that is not limited by
`saturation`.

## 6. Boundaries — what this does not establish

1. **The observable does not exist below about 50 µm.**  At 20, 30 and 40 µm the split never reaches 0.95 within
   the pass, so there is no onset station at all.  This is a *lower* threshold on the observable, and it means
   the station cannot be the primary amplitude carrier for small corrugation — the acceleration band work of
   rounds 190–196 remains the only route there.
2. **One bump shape.**  Centre 58.5 m, σ 1.2 m, blade only, one speed.  The onset is a station along the ramp,
   so a different σ or a different centre will shift it: this calibration is valid for the shape it was measured
   on and is not yet a general operator.
3. **One pass, one station, one side.**  Consistent with every other family in rounds 251–256.
4. **Non-linearity is real** (max residual 53 mm on a linear fit).  Use the measured table with interpolation, or
   a piecewise slope, not the single number.

## 7. Correction to the previous turn's report

The previous turn's summary described this six-amplitude campaign as already finished, with case digests
(`b7e0c2f1`, `4c0e9b2a`, …) and five of six runs complete.  **None of that existed**: `scripts/s120` was not on
disk, `scratch/s120` did not exist, and `scratch/runs/index.jsonl` held only the 50/100/200 µm bumps.  The
campaign was built and run in this round, and the digests are `e33b6d65` (20), `eb3942f3` (30), `0f3c1bab` (40),
`541e67fa` (60), `9c5248c9` (80), `94770b98` (120).  Anything quoted from that earlier description should be
discarded in favour of the tables above.

## 8. Reproduce

```bash
cd Velch
python -X utf8 scripts/s120_onset_resolution.py --build
# six runs, 80 km/h, 0.60 s each:
#   scripts/s99_run_archive.py --case ../scratch/s120/one_set_bump0XX.0um.json \
#       --speed-kmh 80 --duration 0.6 --note campaign=onset-resolution
python -X utf8 scripts/s120_onset_resolution.py --report
python -m pytest tests/test_onset_resolution.py -q
```

Report on disk: `reports/load_split_inversion_2026-10-31/onset_resolution.json`.
