# The onset station is anchored to the ramp, not to the bump (round 258, 2026-10-31)

Round 257 measured the station at which the blade's load share reaches 0.95 and found that it carried the
amplitude of a known Gaussian bump, down to 1.4-4.7 um per output frame. A calibration measured at one bump
shape is not an operator, so this round asked a single question: **does the onset move predictably when the
bump is narrower or sits somewhere else?**

The pre-registered answer was a collapse hypothesis,

```
onset - centre = sigma * F(amplitude)
```

with two consequences testable by four runs at one amplitude: the offset should scale with `sigma` (0.5x at
0.6 m, 2.0x at 2.4 m against the measured -244 mm at 1.2 m), and it should translate with the bump centre. Both
tests are written into `scripts/s121_shape_collapse.py` before any of the runs existed.

**The hypothesis is refuted on both axes, and what replaces it is more useful than the collapse would have been.**

## 1. What was run

Four variants of the canonical one-set case, each a Gaussian bump of 100 um on the blade bodies only
(`sigma`/`centre` varied, everything else inherited including `LMA_x4.prw` and `seat_lateral`), 0.6 s at
80 km/h, all **1201 frames, seven gates 7/7**:

| variant | run id |
|---|---|
| sigma 0.6 m, centre 58.5 m | `one_set_shape_s0.6_c58.5-080.00kmh-0.6000s-500us-b0df017f` |
| sigma 2.4 m, centre 58.5 m | `one_set_shape_s2.4_c58.5-080.00kmh-0.6000s-500us-9ec637f1` |
| sigma 1.2 m, centre 57.5 m | `one_set_shape_s1.2_c57.5-080.00kmh-0.6000s-500us-cd137f76` |
| sigma 1.2 m, centre 59.5 m | `one_set_shape_s1.2_c59.5-080.00kmh-0.6000s-500us-0e17b8ff` |
| sigma 1.2 m, centre 58.5 m (round 257) | `one_set_bump100.0um-080.00kmh-0.6000s-500us-cad4db6b` |

## 2. What was measured

```
sigma 1.2 centre 58.5  onset 58.256 m  offset  -244.4 mm   (reference, round 257)
sigma 0.6 centre 58.5  onset 58.278 m  offset  -222.2 mm
sigma 2.4 centre 58.5  onset 58.244 m  offset  -255.6 mm
sigma 1.2 centre 57.5  onset 58.322 m  offset  +822.2 mm
sigma 1.2 centre 59.5  onset 58.389 m  offset -1111.1 mm
```

Two readings, and the second one is the interesting one:

- **`sigma` axis**: the offset is monotone in `sigma` but moves only 33 mm for a 4x change in width. The
  proportional prediction asked for -122 mm and -489 mm; the measurement gives -222 mm and -256 mm.
- **centre axis**: moving the bump +-1 m moves the onset by **+66 mm and -67 mm**, not by 1 m. In other words
  the onset does not follow the bump at all — it stays at ~58.3 m wherever the bump is put.

So the onset is **anchored to the blade's own lowering ramp** (which arrives at the riding surface around
58.2-58.4 m in this case), and a bump only shifts the crossing a little along that ramp. That is the opposite
of the hypothesis, and it is good news for the operator: the calibration table from round 257 is a property of
the ramp and the amplitude, not of the individual bump.

## 3. What this licenses, and its size

Across all four shapes the onset spans **144 mm**; across 50..200 um at one shape round 257 measured **511 mm**.
Amplitude therefore dominates shape and position by a factor of **3.5**, and one table covers every shape that
overlaps this ramp.

The size matters, and it is not comfortable. Near 100 um the local slope is about **3.3 mm/um**, so 144 mm of
shape/position scatter converts to about **44 um** of amplitude error. That is **twice the 22 um absolute gate**.
The correct statement is therefore:

> the onset station is a usable amplitude observable for bumps on the design ramp with a known shape class,
> and its shape/position bias of ~44 um must be budgeted, not ignored. It does not, on its own, carry an
> absolute amplitude to 22 um.

The domain is also bounded: the crossing only exists where the ramp does. A bump sitting where the blade is
already flush with the stock (roughly beyond 60 m in this case) never drives the share to 0.95, which is the same
mechanism that left 20/30/40 um "never saturating" in round 257 — a bump below ~50 um does not move the crossing
at all, and small corrugation must keep using the axle-box band amplitudes of rounds 190-196.

## 4. What was not tested

- one amplitude (100 um) on the two axes, so `F(amplitude)` is transferred from round 257, not re-measured;
- `sigma` only 0.6/1.2/2.4 m and centre only 57.5/58.5/59.5 m — "consistent with being insensitive" is measured
  inside that box, not proven outside it;
- one speed (80 km/h), one side, one pass, blade bodies only. A `sigma` this large (2.4 m) also changes the
  ramp's own geometry near the crossing, which cannot be separated from a pure "shape" effect with three widths.

## 5. Reproduction

```bash
cd Velch
PYTHONPATH=src python -X utf8 scripts/s121_shape_collapse.py --build
for f in one_set_shape_s0.6_c58.5 one_set_shape_s2.4_c58.5 one_set_shape_s1.2_c57.5 one_set_shape_s1.2_c59.5; do
  PYTHONPATH=src python -X utf8 scripts/s99_run_archive.py \
    --case "F:/ai道岔状态反演辨识/scratch/s121/$f.json" --speed-kmh 80 --duration 0.6 \
    --note campaign=shape-collapse
done
PYTHONPATH=src python -X utf8 scripts/s121_shape_collapse.py --report
```

Report: `reports/load_split_inversion_2026-10-31/shape_collapse.json`.
Tests: `tests/test_shape_collapse.py` (10 items; the corpus one pins this finding, including that both
pre-registered collapses stay refuted).
