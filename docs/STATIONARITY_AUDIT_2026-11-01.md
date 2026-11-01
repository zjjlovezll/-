# Stationarity audit: which archived runs may be quoted

Date: 2026-11-01 · rounds 310–311 · `scripts/s164_stationarity_audit.py`

## 1. Why this exists

Round 310 found that the 60 km/h archive never settled: the front right rail's normal force swings from 0 to
207.75 kN with a standard deviation of 34.75 kN, and the blade engages **nine times** inside one 0.8 m window.
The other two speeds hold 0.07 kN and 0.51 kN and engage once.

The seven numerical gates all passed on that run — they test finiteness, preload residual, penetration, the
friction bound, edge-limited contact, action–reaction and completion, and **none of them tests whether the run
has settled**. So a tripped run can be quoted as if it were a measurement, and the numbers it produces
(`engage`, a fit's amplitude and centre, a gate pass) are artefacts of when a detector happened to cross.

The 60 km/h row has since been withdrawn. The open question this round answers is bigger than that row: **which
of the other archives were taken before their contact load settled, and are any of them carrying a gate?**

## 2. The test, fixed before the audit ran

```
stationary  <=>  max over the eight rails of  std(normal force over the run window)  <  5 kN
```

Five kilonewtons is not a physical constant; it is placed a factor of **48** below the measured failure
(34.75 kN) and a factor of **10** above the worst legitimate row (0.51 kN), so the test separates the known
case without being tuned to it.

A second column is reported as a **diagnostic, not a gate**: the modal block's (coordinates 102:234) norm at the
first frame divided by its norm at the last. The round-310 failure mode was precisely a modal transient that
never decayed, so this column names the mechanism even when the force happens to look quiet.

Nothing is rewritten. The archive index and the `series.npz` files stay as they are; the report only names what
may be quoted.

## 3. Result: 63 archives, 61 stationary, 2 quarantined

```
runs 63   stationary 61   quarantined 2
  quarantined: one_set_x46-060.00kmh-0.0200s-500us-83e727fc
  quarantined: one_set_x46-060.00kmh-0.5400s-500us-83e727fc
gates true but not stationary: the same two
```

The quarantined pair is exactly the 60 km/h null route, at 0.02 s and 0.54 s. **No other archive fails**, and
the two that fail are also the only two whose gate dictionaries are all true — so the audit's quarantine list
and its "gates true but not stationary" list coincide, which is the check that the gate page needed.

## 4. What this protects

Every archive that carries a gate number for the 80 and 100 km/h rows is stationary:

| archive | max rail std | modal decay |
|---|---|---|
| `one_set_x30_bump060.0um-080.0kmh-1.0000s` | 0.25 kN | 1.005 |
| `one_set_bump060.0um-100.00kmh-0.6000s` | 0.32 kN | 1.021 |
| `one_set_x46_bump060.0um-100.00kmh-0.3300s` | 0.72 kN | **2.164** |
| `one_set_threepeak-080.00kmh-0.6000s` | 0.26 kN | 1.053 |
| `one_set_random-080.00kmh-0.6000s` | 0.24 kN | 1.042 |
| `one_set_shape_*` (four) | 0.31–0.35 kN | 1.008–1.076 |
| `one_set_slope_*` (four) | 0.22–0.80 kN | 1.021–1.061 |
| `one_set_lat_y*` (five) | 0.20 kN | 1.023 |

So round 303's four-gate table (80 and 100 km/h) is **not** affected by round 310's withdrawal: those runs hold
their load. The 60 km/h row stays out until it is rerun.

## 5. A watch item, recorded rather than hidden

`one_set_x46_bump060.0um-100.00kmh-0.3300s` passes the force test (0.72 kN) but its modal block **grows** by a
factor of 2.164 across the 0.33 s window. A longer run at that route may therefore drift in position even though
its load looks quiet, and the 100 km/h location row (0.419 m, already outside the 0.20 m tolerance) is the one
most exposed to it. This is reported as `modal_decay` in the audit and as `unsettled_modal` in the verdict; it is
not converted into a gate because 0.33 s is shorter than any modal time constant, so a growth ratio there is
evidence that the block is still moving, not evidence of an unstable run.

## 6. How the gate page consumes it

`s156_gate_page.py` now resolves a **run id** through `s113_profile_inference._index_rows()` and asks the audit
about that run, rather than about a route name:

- `_run_id(route, speed_kmh, duration_s)` — the index row whose route, speed and duration match the campaign's;
- `_stationary_run(run_id)` — the audit's `rows` entry;
- `_stationary(speed, route, duration)` — prefers the audit, falls back to round 310's per-speed report;
- per row: `stationary` (null route), `stationary_bump` (bump route), `gates_quotable` (neither is False);
- `verdict()["gates_quotable"]` reports the pair per speed.

Why per route: the gates read the **bump** archive while the physical column reads the **null** one, and at
60 km/h only the null archive exists. Asking one question for both would either block a quotable row or admit a
tripped one.

## 7. The trap this round hit

The campaign's route string and the archive's `meta["route"]` are not the same text: the campaign asks for
`one_set_x46_bump060.0um` and the run records `one_set_bump060.0um`. Keying a lookup by `route|speed` therefore
silently misses. The audit still emits `by_route_speed` (taking the longest archive per pair) because that view is
useful for reading, but the gate wiring keys on **`run_id`**, which is identical in the index and in the run
directory.

## 8. Recompute

```
python -X utf8 scripts/s164_stationarity_audit.py         # 5 s, writes reports/.../stationarity_audit.json
python -X utf8 scripts/s156_gate_page.py                  # 3 s, four gates + stationarity per speed
python -X utf8 -m pytest tests/test_stationarity_audit.py tests/test_gate_page.py -q
```

Limits: the test is on the **normal force** only (a creep-force ring would not be caught), it is applied to
archives that exist, and it says nothing about runs that were never archived. The 5 kN threshold is a separation
of the two observed populations, not a physical settling criterion; a run that rings at 4 kN would pass.
