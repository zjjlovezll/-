# Held-out coverage, and why the measured verdict had to be made reproducible first

Round 10 of the current goal. Two products: the pipeline's uncertainty layer stops being `skipped` and gets a
**measured** held-out number, and the measured verdict stops depending on a scratch directory outside git.

Everything below is computed by `scripts/s41_coverage.py` from `reports/inversion_measured_2026-10-28/speed_table.json`
and by `scripts/s24_verdict.py` from the four input JSONs now committed beside it. No simulation runs here.

## 1. Why a held-out test is possible on this dataset at all

The dataset has no roughness profile, so almost nothing in it has a ground truth. One quantity does: **the
dominant corrugation wavelength**. It belongs to the track, not to the pass, and the same track was recorded
four times at four steady speeds. Four passes are therefore four independent measurements of one number, and
holding one pass out is a genuine out-of-sample test of any interval the pipeline quotes for it.

Pre-registered before the coverage was computed (written into the script's docstring, not chosen after
seeing the result):

* interval = prediction interval for **one new observation**, `mu ± k·s·sqrt(1 + 1/n_train)`, with `mu`, `s`
  from the three training folds only (`s` with `ddof = 1`);
* the layer passes only if **1σ coverage ≥ 0.50**, **2σ coverage = 1.00**, and **no fold exceeds |z| = 3**.

The second clause is the load-bearing one: an interval that misses a held-out record at two sigma is not a
two-sigma interval, whatever its nominal confidence says.

## 2. The folds

Estimand `median_wavelength_in_band_mm` (the in-band median, i.e. only windows whose strongest line fell
inside the corrugation band — the same population the detector scores).

| held out | value (mm) | train mean | train s | σ_pred | z | 1σ | 2σ | 95 % |
|---|---|---|---|---|---|---|---|---|
| `Run_40kmh_E2toE1.mat` | 28.062 | 27.107 | 1.157 | 1.336 | **+0.71** | yes | yes | yes |
| `Run_50kmh_E1toE2.mat` | 28.427 | 26.986 | 0.950 | 1.096 | **+1.31** | no | yes | yes |
| `Run_60kmh_E2toE1 (1).mat` | 26.265 | 27.706 | 0.949 | 1.096 | **−1.31** | no | yes | yes |
| `Run_75kmh_E1toE2.mat` | 26.630 | 27.585 | 1.157 | 1.336 | **−0.71** | yes | yes | yes |

```
coverage 1 sigma 0.50 (bar >= 0.50)   2 sigma 1.00 (bar = 1.00)   max |z| 1.31
binomial tail: P(X<=2) = 0.379 at 1 sigma, 1.000 at 2 sigma
verdict: PASSED
```

**This is a pass at the weakest possible margin.** Two of four sit exactly on the 1σ bar; one more miss would
fail the layer. The binomial tail says the same thing numerically: four folds cannot distinguish a calibrated
interval from a mediocre one — they can only refute one. So the honest reading is *"not refuted, and the
2σ clause does hold: no held-out pass is more than 1.31σ from its prediction"*. It is not "the σ is
validated".

## 3. The sensitivity decides which observable is defensible

The same folds on `median_wavelength_mm` (all windows, not only in-band ones):

```
coverage 1 sigma 0.50   2 sigma 0.75   max |z| 3.06   → FAILED
```

One fold lands at **3.06σ**. So the all-window median has a fat tail the in-band median does not: its
strongest line sometimes sits outside the corrugation band, and that inflates the scatter in a way the
prediction interval does not absorb. The in-band median is therefore the defensible speed-independent
observable, and the all-window one may not be quoted as a repeated measurement.

This is a conclusion about the **estimator**, measured on the same four records, not a preference.

## 4. The second uncertainty source, and why it matters more

Coverage answers "is the interval the right width for this estimand". It does not answer "is a ±2 dB band
amplitude reachable". For that, the relevant number is the estimator's own spread between two records of the
**same spectral class** (rounds 194/195, two test seeds, same bands, same channel):

| band (m) | \|Δerror\| between the two same-class records |
|---|---|
| 0.1000–0.1316 | **1.96 dB** |
| 0.1316–0.1732 | **1.78 dB** |
| 0.1732–0.2280 | 0.54 dB |
| 0.2280–0.3000 | **1.78 dB** |

Three of four bands move by ≳1.8 dB between two records of the same class — **comparable to the entire ±2 dB
budget**. A ±2 dB claim would therefore need averaging over several records of the class, and this dataset
does not contain them. This is scatter, not coverage: two seeds per band cannot support a coverage claim, and
the layer's notes say so.

## 5. What changed in the verdict

`reports/inversion_measured_2026-10-28/verdict.json`:

| layer | before | now | why |
|---|---|---|---|
| L0 admission | passed | passed | unchanged |
| L1 registration | passed | passed | unchanged |
| L2 calibration | passed | passed | unchanged |
| L3 inversion | passed (spectral) | passed (spectral) | unchanged |
| **L4 uncertainty** | **skipped** | **passed** | held-out coverage measured, criterion met at the boundary |
| L5 acceptance | failed | failed | 3 of 6 sections, bar is 6 of 6 |

Derived status stays **`detection_only`** — adding a passing uncertainty layer does not license an amplitude
or profile claim, because L5 is still failed and the repeatability above is of the same size as the budget.

## 6. Reproducibility: the verdict used to live on one machine

`reports/` is ignored by git (`.gitignore:42`). The measured artefacts were written to disk but **never
committed**, and `s24_verdict.py` read its four inputs from `F:\velch_tmp` — a scratch directory outside the
repository. On a clean checkout every layer would have fallen back to `skipped`, which reads like "nothing was
established" when it means "the inputs were never committed".

Closed this round:

* `reports/inversion_measured_2026-10-28/inputs/` now holds the four inputs (`oma_ALL_Run_75kmh_E1toE2.json`,
  `fdd_sections.json`, `speed_separation.json`, `speed_table.json`) plus `detection.json`;
* `s24_verdict.py` resolves each input as **committed copy first, scratch second**, so the evidence strings in
  the verdict name files that are in the repository and the output does not depend on machine state;
* verified by deleting the scratch `coverage.json` and re-running: the regenerated `verdict.json` is
  **byte-identical** (sha256 `ae79a756…`, same six layer statuses, same L4 metrics);
* the synthetic route also gained its missing `windows.csv` (8 rows: seed × band, window 0.127985–0.281568 s,
  42.5–45.5 m, bins kept 7/5/4/3, energy fraction 0.99), so gate 5's artefact set
  `verdict.json + bands.csv + windows.csv` is complete for both routes.

## 7. Boundaries — what this does not establish

1. **n = 4 folds.** Coverage can only be 0, 0.25, 0.5, 0.75 or 1; a single miss moves it a quarter. Four
   folds refute, they do not calibrate.
2. **The four passes share the sections**, so the folds are not independent measurements of *six* quantities —
   one wavelength per pass. Nothing here says anything per section.
3. **The estimand is the wavelength.** No amplitude or depth enters this test, because the dataset has no
   profile truth to test one against.
4. **Two of the four passes run the opposite direction.** Direction is a possible explanation for the 26.3 mm
   pair sitting 1.3σ low, and it is not separable with four records; it is recorded, not modelled.
5. **`physics_validation_status` is untouched** — still `unvalidated_against_measurement_or_Simpack`.

## 8. Recompute

```
cd F:\ai道岔状态反演辨识\Velch
PYTHONPATH=src python -X utf8 scripts/s41_coverage.py        # folds, coverage, criterion -> coverage.json
PYTHONPATH=src python -X utf8 scripts/s24_verdict.py         # re-assembles the six layers from the inputs
PYTHONPATH=src python -X utf8 scripts/s40_band_verdict.py    # synthetic route: verdict + bands + windows
PYTHONPATH=src python -X utf8 -m pytest tests/test_coverage.py -q
```
