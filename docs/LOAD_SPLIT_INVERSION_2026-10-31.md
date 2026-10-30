# Inverting the bump out of the load split (M5, step 2)

Date: 2026-10-31. Script: [`../scripts/s113_profile_inversion.py`](../scripts/s113_profile_inversion.py).
Report: [`../reports/load_split_inversion_2026-10-31/inversion.json`](../reports/load_split_inversion_2026-10-31/inversion.json).

Round 250 measured that the axle-box acceleration localises a bump but stops being monotone past about
0.8 of the static penetration, while the split between the two bodies of the right rail keeps moving.
This round takes that split and inverts it for a station-resolved profile `z(s)` on the contact band —
the first station-resolved inversion in the programme, and the first one with a truth to compare against.

## 1. Observable, geometry, estimator

Per output frame the axle sits at `s = x_start + v t + offset[axle]` (offsets from the case, not the
meta — the meta does not store them). The split is

```
sigma(s) = blade / (stock + blade)        in [0, 1], masked where the total is under 1 kN
```

and the known geometry is the pristine crown gap measured from the canonical case's own two bodies,

```
d(s) = stock_crown(s) - blade_crown(s)    positive = the blade is lower
   d(57 m) = +324 um    d(58.5 m) = -9 um    d(60 m) = -14 um
```

A bump of amplitude `z` raises the blade, so the gap the contact sees is `u = d - z`.

The estimator is a monotone table `sigma = f(u)` built from **one** amplitude (50 µm, the linear one)
by binning the samples into 40 quantile bins and taking medians, then inverted by interpolation:
`u = f^-1(sigma)`, `z = d - u`. The 100 µm and 200 µm runs never enter the calibration, so their errors
are hold-out errors. The split is median-filtered over 0.20 m before inversion (the feature is 1 m
wide; a single frame flickers between the bodies).

## 2. Pre-registered gates

| gate | criterion |
|---|---|
| G-A | `|ŷ − y| / max(y, 0.5 mm) ≤ 2 %` (the user's 98 % criterion, against the decided floor) |
| G-B | `p95(|e|) ≤ 22 µm` over the window where the truth exceeds 10 % of its peak |
| G-C | the station of the inverted peak is within 0.20 m of 58.5 m |

## 3. Measured

```
calibration table from 50 um only: 40 bins, u -58.6 .. 14168.8 um, sigma 0.935 .. 0.000

amplitude   peak_true   peak_est   rel err   p95 |e|    max |e|   peak at   A/B/C
       50        50.0       56.8    0.0137     15.05      23.11     58.36   Y/Y/Y
      100       100.0       76.5    0.0469     48.95      61.94     58.24   n/n/n
      200       200.0      101.7    0.1966    147.50     161.60     57.98   n/n/n
```

**Hold-out verdict: fails.** The two amplitudes the calibration never saw are under-recovered by
23.5 % and 49.2 %, with p95 errors 49 µm and 148 µm — an order of magnitude over the absolute gate.

## 4. Why — the table has a range, and the bump leaves it

The calibration table spans `u ∈ [-58.6, +14169] µm`, because the 50 µm run never produced a closer
gap than that. A 100 µm bump drives `u` to about `-109 µm` and a 200 µm bump to `-209 µm` — both
**outside the table**, where the estimator clamps to the smallest `u` it knows. The recovered
amplitude is therefore bounded by the calibration amplitude's reach, which is exactly what the numbers
show: 76.5 µm for a 100 µm bump, 101.7 µm for a 200 µm bump.

So this is an **extrapolation failure of the calibration set, not evidence that the split carries no
amplitude information.** The 50 µm row makes the opposite point: within the calibrated range the same
estimator recovers the peak to +13.7 % and the profile to `p95 = 15.1 µm` (0.23 × the static
penetration) with the peak at 58.36 m (0.14 m from truth).

## 5. What this fixes for the next step

1. **The calibration must span the amplitude range it will be asked about**, or be re-parametrised:
   `u` is known once `z` is known, and `z` can come from a contact model rather than from a table of
   one amplitude's samples. The cleaner estimator is `sigma = f(d - z; N)` fitted jointly over
   several amplitudes, with the amplitude entering as the parameter to be solved for — which is
   exactly the M7 form.
2. **Frames where the blade is not carrying are unobserved, not zero.** Before the gap closes every
   frame reports `sigma = 0`; inverting them would report "no bump" as a measurement. The script masks
   them (`sigma > 0.02`) and reports how many frames survive.
3. The station-localisation part of the inverse is already good: every peak landed within 0.52 m of
   the truth, and the 50 µm case within 0.14 m.

## 6. Boundaries

One speed (80 km/h), one station (58.5 m), one σ (1.2 m), three amplitudes, blade body only, straight
route, and the calibration table is built from a single run. The gates are the pre-registered ones in
the task book; none was changed after seeing the numbers.

## 7. Recompute

```bash
cd Velch
export PYTHONPATH=src
python -X utf8 scripts/s113_profile_inversion.py
python -X utf8 -m pytest tests/test_load_split_inversion.py -q
```
