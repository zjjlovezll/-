# Putting the contact model inside the inversion (M5, step 4)

Date: 2026-10-31. Script: [`../scripts/s115_model_inversion.py`](../scripts/s115_model_inversion.py).
Report: [`../reports/load_split_inversion_2026-10-31/model.json`](../reports/load_split_inversion_2026-10-31/model.json).
Previous steps: [M5.1](SURFACE_SENSITIVITY_2026-10-31.md), [M5.2](LOAD_SPLIT_INVERSION_2026-10-31.md),
[M5.3](THREE_ESTIMATORS_2026-10-31.md).

Round 252 concluded that no one-dimensional map `sigma = f(u)` can work, because the gap at which the load
halves moves with the amplitude. The prescribed fix was to put a forward model of the split inside the
inversion. This round does that, and it still does not pass — which is the round's result, and it narrows
what is missing.

## 1. The model

Both bodies carry the measured axle load `N` through strip contacts,

```
F = C * max(0, penetration) ** 1.5        one C per body: C_stock, C_blade
stock_pen = p - max(0, -g)                blade_pen = p - max(0, g)
F_stock + F_blade = N                     -> solve the common wheel height p by bisection
sigma_pred = F_blade / N                  g = d(s) - z(s)
```

The stock clipping at zero is the branch that round 250 measured (zero-force frames 0 / 37 / 161). The
inversion is a root find per frame: the `g` that reproduces the measured `sigma`, then `z = d - g`. There
is no table, so nothing to run off the end of.

Two parameters for the whole dataset, fitted on two amplitudes and applied to the third.

## 2. Measured

```
fold  calibration      C_stock          C_blade      held out  peak_true  peak_est  p95 (um)  at s
      (100, 200)       4.704e10         4.033e10     50        50.0      102.8     63.5    58.51   n/n/Y
      (50, 200)        5.426e10         4.613e10     100      100.0      129.7     88.6    58.29   n/n/n
      (50, 100)        1.276e11         7.998e10     200      200.0      121.7    113.9    58.02   n/n/n
```

0/3 folds pass. The fitted stiffnesses land in the physical range (frozen contact stiffness is
1.1267e11 N/m^1.5), so the model is not absurd — but it **over-reads** the small bump (102.8 for 50 µm)
and **under-reads** the large one (121.7 for 200 µm), i.e. it compresses the amplitude scale.

## 3. What the failure says

The model represents the load split, but it assumes the geometric gap is the whole story. It is not: in
the canonical case the rail is `local_compliant` — the body sinks by tens of micrometres under load, and
that sink is of the same order as the bump being measured. Two consequences:

1. the effective `g` the contact feels is `d - z + (rail sink difference)`, and the sink difference
   between the two bodies is not in the model;
2. because the sink is load-dependent, it couples back into `p`, which is why the fit lands on a softer
   `C` for the folds that see the smaller amplitudes and a stiffer one for the fold that sees both large
   ones (4.7e10 vs 1.28e11).

So the missing physics is identified: **the two bodies' support compliance must be in the inversion**, not
just their contact stiffness.

## 4. The four families, side by side

| family | free parameters | 50 µm | 100 µm | 200 µm | failure mode |
|---|---|---|---|---|---|
| table (M5.2) | 40 bins | +13.7 % | −23.5 % | −49.2 % | clamps at the table edge |
| tanh map (M5.3) | 2 | +155 % | +117 % | +13 % | amplifies near σ = 1 |
| transfer station (M5.3) | 0 | −27.4 µm | −56.1 µm | −107.4 µm | half-load gap moves with amplitude |
| contact model (this round) | 2 | +106 % | +29.7 % | −39.2 % | ignores support compliance |

Four families, four different failure modes, and none passes. That is a strong statement about the
measurement rather than about the estimators: at these amplitudes, **one pass of one axle does not
determine the bump amplitude.**

## 5. What that fixes for the next step

- **The ensemble is no longer an option, it is the mechanism.** M4's arithmetic already required ≥ 3
  lateral offsets for a surface claim; the amplitude now needs it too, because each pass contributes one
  transfer-station constraint and the branch it lands on depends on the lateral position.
- **The forward model for the ensemble must include both bodies' support compliance**; without it the
  same compression of the amplitude scale will reappear.
- **Localisation is the part that works** in every family (0.14 m in range, ≤ 0.52 m across all).

## 6. Boundaries and recompute

One speed, one centre, one σ, three amplitudes, blade body only, straight route; gates unchanged. The
support compliance of the two bodies is currently *outside* the model — stated as the identified gap, not
absorbed into a fitted constant.

```bash
cd Velch
export PYTHONPATH=src
python -X utf8 scripts/s115_model_inversion.py
python -X utf8 -m pytest tests/test_model_inversion.py -q
```
