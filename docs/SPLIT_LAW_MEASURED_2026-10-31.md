# Where the amplitude compression actually comes from: the split law, measured

Date: 2026-10-31. Scripts: [`../scripts/s116_support_sink.py`](../scripts/s116_support_sink.py),
[`../scripts/s117_split_law.py`](../scripts/s117_split_law.py). Reports:
[`../reports/load_split_inversion_2026-10-31/support_sink.json`](../reports/load_split_inversion_2026-10-31/support_sink.json),
[`../reports/load_split_inversion_2026-10-31/split_law.json`](../reports/load_split_inversion_2026-10-31/split_law.json).

Round 253 blamed the amplitude compression on "the two bodies' support compliance". This round tested that
before it earned another paragraph, found it false, and then measured the mechanism that remains.

## 1. The support compliance is common mode — round 253 was wrong

The `local_compliant` track carries **one node pair per rail** (`y`,`z`), and the right rail's stock and
blade are two *bodies on that same node*. Seated, all eight rails sink by the same amount:

```
rail               sink (um)  force (kN)  F/sink (N/m)
axle1_left        -1202.6962       60.15    -5.002e+07
axle1_right       -1202.6962       60.15    -5.002e+07
...               (all eight identical)
sink span across rails  0.00 um
```

`F/sink = −5.002e7 N/m` against the case's `k_z = 5.0e7 N/m`: the node does what the support says. The
sign convention is negative = down, magnitude 1.2027 mm = 60.15 kN / 5.0e7.

The consequence is structural: `d(s) = stock − blade` is a **difference of two surfaces on the same node**,
so any common descent cancels from it, and it does — the span across rails is identically zero. Two bodies
sharing a node cannot sink differently, so **support compliance cannot distort the gap**, and round 253's
named mechanism is retired. (Recorded rather than quietly deleted: it was stated in a commit message and in
the changelog.)

## 2. So measure the law itself

Lift or lower the whole blade body by a known offset, re-seat, and read the split the real solver produces.
The probe has to sit inside the blade's mileage range (50.578–104.419 m), so the front axle is seated at
**58.0 m** (x_start 48.0 + the 10 m front-axle offset), not at the canonical 50.0 m.

```
offset (um)  stock (kN)  blade (kN)  sigma   half width (mm)  lever_y (mm)
    -250.0        0.00       60.20   1.0000       6.000        754.393
    -150.0        6.05       53.86   0.8990       5.750        754.543
     -80.0       37.95       22.16   0.3687       6.472        751.788
     -40.0       55.71        4.45   0.0739       7.468        751.582
     -20.0       60.15        0.00   0.0000       7.468        751.573
       0.0       60.15        0.00   0.0000       7.468        751.573
     +20.0       60.15        0.00   0.0000       7.468        751.573
    +250.0       60.15        0.00   0.0000       7.468        751.573
```

Negative offset = the blade is raised. Three numbers matter:

1. the split reaches one half at **−97.3 µm** of blade raise;
2. the transition from zero to full blade load occupies about **210 µm** of blade height (σ 0.07 at −40,
   0.90 at −150), i.e. the steepest measured slope is **0.00758 per µm** — a resolution of one micrometre of
   height is worth 0.76 % of the split here;
3. the contact half-width moves **5.750 → 7.468 mm (1.30×)** across that transition, because the blade's
   strip is narrower than the stock's once it carries load.

## 3. That is the compression mechanism

The bumps being inverted are 50 / 100 / 200 µm. The split law's whole dynamic range is 210 µm wide, and the
footprint — hence the effective stiffness of each body — changes by 30 % inside it. A model with **one
stiffness per body** is therefore forced to average over a 30 % change in the thing it is modelling, and it
does so by rescaling the height axis, which is exactly what round 253 measured (50 µm read as 102.8,
200 µm read as 121.7).

## 4. One parametric form that fits the measured law

`sigma = 1 / (1 + (g/g0)^p)` with the blade's excess height `g`:

```
g0 = 72.6 um   p = 6.000   offset 159.4 um      rmse in sigma 0.0280   max |err| 0.1010
```

Six is far from the 1.5 a pure Hertz contact would give, and that is the measurement's point: the law is much
steeper than one stiffness per body implies, for the width reason in §3.

## 5. What this changes for the next step

- The forward model in an estimator must carry **the footprint width as a function of the split**, not a
  single `C` per body. Otherwise the same 30 % is absorbed into the height axis.
- The split law is now a **measured operator** at one station; the next question is whether it moves with
  mileage (it must — the blade's own section narrows towards the tip) and whether it moves with speed.
- The ensemble (≥ 3 lateral offsets, M4) is still the mechanism for the *lateral* direction. This round's
  finding is about the *vertical* channel: the amplitude error is a footprint-width effect, not a
  support-stiffness effect.

## 6. Boundaries and recompute

Single station (58.0 m), single speed (80 km/h), quasi-static probe (seated state evaluated at one frame, no
time integration), blade body only, straight route. The probe moves `run.x_start_m`, so it is a geometric
probe of the split law, not a claim about the dynamic run. The 2-parameter fit is descriptive; no gate was
applied to it and none should be inferred.

```bash
cd Velch
export PYTHONPATH=src
python -X utf8 scripts/s116_support_sink.py
python -X utf8 scripts/s117_split_law.py
python -X utf8 -m pytest tests/test_split_law.py -q
```
