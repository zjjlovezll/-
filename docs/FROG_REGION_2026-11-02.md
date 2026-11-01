# The frog is in the case and can never carry the wheel

Round 317.  Question asked: every archive in this repository stops at or before 70 m, the frog body
spans 103.280-116.440 m, so how were the 80 and 100 km/h runs ever "turnout" runs?  Answer: they were
not — they are windows over the switch blade.  This round tried to reach the frog and found that the
case, as built, cannot hand the wheel to it.

## 1. What was run

| attempt | what | result |
|---|---|---|
| `setups/one_set_passage.json` | 40 → 116 m, 80 km/h, 3.5 s, 0.005 s output | ran about two hours of wall time with no archive written; the job ended without a report |
| `setups/one_set_transfer.json`, seat at 93 m | 0.25 s window starting at 103.0 m | `vertical preload equilibrium failed: no seed converged; gtol` |
| same, seat at 46 m, run from 93 m | the first seat converges, the second (after the modal settle) does not | `... no seed converged; xtol` |
| `s158.seat_at` at 100.0 and 103.0 m | static equilibrium only | `xtol` and `gtol`, both "no seed converged" |

So the frog region is not merely unreached: **a z-only static equilibrium does not exist there** in
this case.  That is a geometric statement and it can be read off the sections.

## 2. What the sections say (measured, no simulation)

Right rail at four stations, crown = `max(z)` (z points down, so the crown is the maximum; the
`min(z)` mistake is B049):

| station (m) | stock crown | blade crown | frog crown |
|---|---|---|---|
| 90.00 | **+0.072 mm** | +0.072 | — |
| 103.28 | **+0.072** | +0.000 | **−13.962** |
| 103.50 | **+0.072** | +0.000 | −6.965 |
| 104.10 | **+0.072** | +0.000 | −1.567 |
| 104.42 | **+0.072** | — | −0.040 |
| 105.50 | **+0.072** | — | −0.000 |

Two facts follow, and together they decide the question:

1. **The frog carries the designed lowering.** −13.962 mm at the nose, zero by 104.42 m.  (The design
   table says 13.5 mm at 103.280 m; the 0.46 mm difference is the same discretisation that already
   shows up elsewhere, and it is not the problem.)
2. **The stock rail runs through the crossing.** Its crown is +0.072 mm at every station from 90 m to
   116 m.  The frog tops out at 0.000 mm — **0.072 mm below the running surface** — so it never
   touches the wheel.  There is nothing to transfer: the wheel is on the stock rail the whole way.

The seat fails for the same reason: three bodies present a crown within 0.072 mm of each other at the
same lateral position (`y = +759.5 mm`), so "which surface carries the deepest contact" is decided by
0.07 mm of discretisation rather than by geometry, and the vertical solve has no unique answer to
converge to.

## 3. What this means for the goal

`Ω_obs` (the running band) cannot include the frog until the crossing is built as a crossing.  The
model needs, in this order:

1. **interrupt the stock rail** over the crossing (its running surface is replaced by the wing rail
   there) — currently one body spans 0-1000 m and shadows everything;
2. **two bodies at the frog**: wing rail and long point rail, each with its own `s_lo_m`/`s_hi_m`, so
   the load can move from one to the other;
3. **a check rail** (护轨) on the opposite side — without it a centred wheelset has no lateral datum
   inside the flangeway, which is exactly the degeneracy measured above.

Acceptance for the next run (pre-registered here, before it is attempted):

- at 103.28 m the `frog` body carries 0 kN and the wing rail carries the axle load; by 105.0 m the
  frog carries ≥90 % of it;
- the transfer mileage moves by ≤0.10 m when the same window is run at 100 km/h;
- the sum over bodies equals the rail total to ≤1 N in every frame;
- gates all true, or the failing gate named; `freeze_baseline --check` UNCHANGED.

## 4. What can and cannot be said

**Can be said**: the frog body and its lowering are in the case (13.962 mm at the nose, measured); the
stock rail is continuous through 90-116 m at +0.072 mm; the frog's crown never rises above 0.000 mm,
so it never contacts; a z-only seat inside 93-103 m fails in two different solvers (gtol, xtol).

**Cannot be said**: that the frog geometry is wrong in the design; that a transfer is impossible in
reality; that the 80/100 km/h results are invalid for the blade region they actually cover.

## 5. Reproduction

```
python -X utf8 -m pytest tests/test_frog_region.py -q      # 5 passed, 1.6 s
python -X utf8 scripts/s173_frog_passage.py --setup setups/one_set_transfer.json \
    --report reports/frog_passage_2026-11-01/transfer.json   # seat inside the crossing: gtol
```
