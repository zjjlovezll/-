# The reference station a load split predicts for 5 % blade share — and why it is 0.30 m short

Round 303 measured where the blade first carries 5 % of the axle load (58.156 m at 80 km/h, 58.153 m at
100 km/h) and had to leave the physical location gate suspended: those stations sit 0.423 m past the
calibrated touch (57.733 m) and 0.267 m short of flush (58.423 m), and nothing in the archive said where
inside that interval a 5 % share *ought* to fall. This round supplies that missing reference by an
independent route — a two-spring load split driven by the case's own crown gap and the frozen contact
stiffness — and it fails, in an informative way.

## 1. What is being compared

```
N_s = C delta_s^1.5,   N_b = C max(delta_s - g, 0)^1.5,   N_s + N_b = W
```

`g` is the crown gap (stock crown minus blade crown, positive when the blade is lower), read from
`../scratch/s146/one_set_x46.json`'s own station table through each body's `ProfileSeries` (`max(z)`,
since a lowered blade shifts the whole profile down). `C` is taken from the frozen oracle
(`59 680.57685863 N` at `65.4661 um` ⇒ `C = 1.12670e11 N/m^1.5`) and `W` from this case's own mass
(`481 078.5 N / 8 = 60 134.8 N`). **Nothing is fitted**: there is no free parameter in the law, which is
what makes the comparison worth doing.

## 2. The pre-registration

| item | statement |
|---|---|
| `H4` | the 5 % engage station is what the parallel split of the crown gap predicts |
| falsifier | `|s_law(5 %) - s_model(5 %)| >= 0.10 m` (half the 0.20 m physical gate) |
| shape claim | the same law reproduces the measured share curve: correlation `>= 0.99`, rms `<= 0.05` |
| void condition | the crown gap must reproduce the calibrated touch station to within `0.02 m`, otherwise it is not the quantity the solver sees |

The void condition is there because a load-split law built on the wrong gap would be comparing two
different geometries while looking like a physics test.

## 3. Readings

```
stiffness from the frozen oracle 1.1267e+11 N/m^1.5, wheel load 60134.8 N
share at zero gap 50.0 % (the law is symmetric there)
touch   : crown gap 65.47 um at 57.733 m (calibrated 57.733 m, off 0.000 m)
5 %     : crown gap 54.66 um at 57.853 m (law) against 58.156 m (model) -> 0.303 m
crown gap where the model engages: 26.45 um -> the model reports 28.2 um more gap than the crowns give
shape   : rms share difference 0.134 at correlation 0.907 over 161 samples
VERDICT : CROWN-GAP SPLIT NOT SUFFICIENT
```

Three things follow, and the first one is worth as much as the failure.

## 4. Touch is exact, the split is not — and that difference is the finding

**The crown gap reproduces the calibrated touch station to 0.000 m** (57.733 against 57.733). So the
`max(z)` crown gap *is* the quantity the solver sees when the blade first makes contact: touch is
decided by the highest point of each profile, and the widths, lateral offsets and wedge shapes cancel
at that single event.

**But the same gap is 28.2 µm too optimistic for the split.** At the model's engage station the crowns
are 26.45 µm apart, while the law needs 54.66 µm to deliver 5 %. In physical terms the blade is a
wedge whose crest sits inboard of the stock crest; the wheel's rolling circle passes outboard of the
blade crest, so the wheel sees more clearance than crest-to-crest. First contact is insensitive to
that shift (the highest points still meet), the load split is not.

So the 0.303 m is not the model being wrong and it is not the law being wrong: it is **the crown gap
being the wrong abscissa for a share**, which is a statement about geometry that can be tested, not an
excuse.

## 5. What this changes for the gate

- The physical location column **stays suspended**, and now with a reason that is arithmetic rather
  than a shrug: the only law available predicts `57.853 m`, the model reports `58.156 m`, and a
  ±0.20 m gate armed on the law would fail at 0.303 m.
- `centre` remains non-quotable as a physical quantity (round 301); `engage` remains the physical
  column (round 303), with `engage(5 %)` in the interval `[57.733, 58.423]` (61 % of the way).
- The 80/100 km/h agreement (58.156 against 58.153, 3 mm) is unaffected: both were measured the same
  way, and the law's failure is common to both.

## 5b. The 60 km/h null run landed, so the physical column is now three wide

The 0.54 s null run for 60 km/h finished on 2026-11-01 (`scratch/runs/one_set_x46-060.00kmh-0.5400s-500us-83e727fc`,
140 min 37 s, seven gates true). Reading it the same way as the other two gives:

| speed | engage 1 % | engage 5 % | past touch (5 %) |
|---|---|---|---|
| 60 | 57.892 m | **58.000 m** | **+0.267 m** |
| 80 | 58.122 m | 58.156 m | +0.423 m |
| 100 | 58.111 m | 58.153 m | +0.420 m |

So the physical error is **not** speed-independent: it is 0.267 m at 60 km/h against 0.423 / 0.420 m at
80 / 100. All three are outside the 0.20 m tolerance, but the trend says the offset shrinks as speed
drops, which is the opposite of what a pure sampling artefact would do — another reason to keep reading
it physically.

The four synthetic gates cannot be read at 60 km/h yet, because `s152.fit` loads the **bump** route
(index 1) and that run does not exist. `s156` therefore reports the speed as `partial`: its physical
engage is quotable, its gates are withheld rather than printed as absent. That distinction is
load-bearing — `measure()` used to treat a null-only archive as `measured`, so the moment the 60 km/h
null run appeared the page would have raised `SystemExit` on the missing bump route (it did, in the
gate run at 10:59), and a lazier fix would have printed four dashes as a pass.

## 6. Next step this makes necessary

The reference station has to come from the **effective gap at the contact point**, not from the crowns.
The cheap way is a static probe: place the wheel at a station, seat it, and read the blade and stock
penetrations plus the lateral position of each contact — that gives the gap the wheel actually
experiences, and the split law can then be evaluated on the correct abscissa. Ten stations across
`57.4–59.2 m` is enough to check whether the 28 µm is explained by the lateral offset, and it needs no
integration.

## Recompute

```
cd Velch
python -X utf8 scripts/s157_engage_reference.py
python -X utf8 -m pytest tests/test_engage_reference.py -q
```
