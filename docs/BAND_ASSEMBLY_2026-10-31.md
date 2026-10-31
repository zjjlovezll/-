# M7 assembly: one light band, reconstructed end to end — and judged

Round 260.  This is the first time the pieces of rounds 251–259 are wired into a single
reconstruction of the running surface and scored against the gates the task book declared before any
of it ran.  The verdict is a **fail**, and the failure is specific enough to redirect the work.

## 1. What is assembled

| piece | where it comes from |
|---|---|
| observable | `sigma(s) = blade/(stock+blade)` from the archived runs (`s113._split`, median filter) |
| law | width-resolved split law measured on static probes (`s118`, `reports/…/split_law_vs_station.json`), inverted through the measured curve (`s123.build_law`) |
| geometry | design gap `d(s) = stock_crown − blade_crown` from the canonical case (`s113._gap_profile`) |
| zero | the **un-bumped run**: `z_hat(s) = z_run(s) − z_null(s)` |
| truth | the synthetic Gaussian bump injected at 58.5 m, sigma 1.2 m (50 / 100 / 200 µm) |

Two decisions are stated because they change the number:

1. **The null run defines the zero.**  The absolute inversion carries a bias, because the split law
   was measured on a seated model whose wheel already penetrates by the static 63.70 µm while `d(s)`
   is a pure geometric gap.  Both raw and differential numbers are printed; the bias cannot hide.
2. **The filtering window is chosen on the null run only** (the window that leaves the smallest
   background), so the choice cannot lean on the truth.  Measured: 0.10 m → 66.1 µm, 0.20 → 65.6,
   0.30 → 61.7, 0.50 → 51.4, 0.80 → 43.1, 1.20 → 43.1 ⇒ **1.20 m**.

## 2. Result

```
law anchor: 45.2 mm at 58.0 m, half gap +56.15 um, sigma span 0.000..1.000
smoothing chosen on the null run only: 0.10 -> 66.1, 0.20 -> 65.6, 0.30 -> 61.7,
                                      0.50 -> 51.4, 0.80 -> 43.1, 1.20 -> 43.1  => 1.20 m

 amplitude  est peak   p95 um  raw p95  worst 2mm %  peak err m  G-ABS  G-REL  G-LOC
      null     86.83    43.05    43.05            -           -   FAIL      -      -   <- G-NULL
      50.0     97.71    98.10   105.34        29.14       0.344   FAIL   FAIL   FAIL
     100.0    145.50   229.81   230.97        48.29       0.344   FAIL   FAIL   FAIL
     200.0    125.64   180.38   211.40        43.65       0.000   FAIL   FAIL   PASS

0/3 amplitudes pass all three amplitude gates, and G-NULL is missed at 43.1 um against a 16.7 um
limit.  The best reconstruction is 50 um at p95 98.1 um (4.5x the gate).
```

Gates as declared in the task book: `G-ABS` p95 ≤ 22 µm, `G-REL` `|e|/max(|z|, 500 µm) ≤ 2 %` at the
worst 2 mm bin, `G-LOC` peak station ≤ 0.20 m, `G-NULL` background p95 ≤ 16.7 µm.

## 3. What the numbers say

1. **The background is not zero.** 43.1 µm is 2.6× the null limit, and the raw bias is 43–105 µm.
   The absolute inversion has no defined zero; only the differential one has a chance, and even the
   differential leaves 43 µm of background spread.
2. **The amplitude mapping is not monotone.** The reconstruction reads 97.7 / 145.5 / 125.6 µm for
   injected 50 / 100 / 200 µm.  A single-pass amplitude cannot be read off this estimator: the same
   non-monotonicity that round 250 found in the acceleration reappears in the split-derived profile,
   because above ~100 µm the blade takes the whole load (share → 1.0) and the estimator saturates.
3. **Localisation survives where the profile does not.** `G-LOC` passes for 200 µm (0.00 m) and is
   within 0.34 m elsewhere — consistent with rounds 257/259, where position was recoverable to
   0.14–0.52 m from the acceleration while amplitude needed the station observable.
4. **The error budget is dominated by two terms we have already measured.** The law's `u` carries
   ±30 µm (round 256: the 45 mm anchor is the only well-measured one, and 11 of 158 stations clamp),
   and the share carries ±50 µm per station of flicker (the median filter over 1.2 m is what brings
   the background from 66 to 43 µm).  Quadrature: ~58 µm — the measured 98 µm is that plus the
   amplitude-mapping error.

## 4. What this means for M7

Point-by-point profile inversion through the split law **does not reach 22 µm**, and the gates were
not relaxed to hide it.  What the rounds do support, separately and with numbers:

| quantity | accuracy | evidence |
|---|---|---|
| position of a feature along the contact line | 0.14–0.52 m | round 250, acceleration |
| amplitude **above 50 µm** on the ramp | 3.3 mm/µm slope ⇒ 44 µm per 0.1444 m of shape/location spread | rounds 257, 258 |
| amplitude **below 50 µm** | not observable by the station method at all | round 257 |
| lateral extent visible per pass | 4 mm (1 %), 3.6 mm (10 %), 1.7 mm (50 %) | round 259 ⇒ 9 passes for the head |

So the estimator that has to be built next is not a better pointwise inversion of this law.  It is a
**joint fit** with three ingredients: the null run as the zero, the acceleration for position, and the
station observable for amplitude — with the law's width dependence carried as a prior rather than
re-inverted at every station.  The `0/3` printed above is what a single observable family buys.

## 5. Boundaries

* One speed (80 km/h), one bump shape (sigma 1.2 m), one centre (58.5 m), one side (right), one pass.
* The truth is synthetic: this is an estimator test (evidence class B), not a measurement of a real
  rail.  `physics_validation_status` is unchanged.
* Coverage: one pass reconstructs one 4 mm strip = 11 % of the 37.15 mm head (the contact itself is
  16 mm = 43 %).  Accuracy is reported next to coverage on purpose.
* `SIGMA_LO/HI = 0.05/0.95` drops stations where the share is saturated or empty; the window is
  therefore not the full bump.

## 6. Reproduce

```bash
PYTHONIOENCODING=utf-8 python -X utf8 scripts/s123_m7_assembly.py
python -X utf8 -m pytest tests/test_m7_assembly.py -q
```
