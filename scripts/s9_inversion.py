# -*- coding: utf-8 -*-
"""S9-4: run the S7e long-wave inversion on the *flexible* wheelset.

The question is the one the night's taskbook pre-registered: does the flexible wheelset change
what the inversion can recover?  The estimator, the bands, the amplitude and the acceptance gates
are S7e's, imported rather than copied, so the two models are compared by one protocol.

Three differences from ``scripts/s7e_longwave.py``, each forced by cost and each stated in the
result:

* the columns come from **one** differential pair per band instead of eight phase realisations.
  The solver is deterministic and the differential pair removes the case's own geometry exactly,
  so the eight phases were averaging a noise that does not exist here, at a cost of 16
  simulations.  On the flexible model a 2 s run takes about ten minutes: 8 runs is the night,
  20 is not;
* the case is the axle-box vehicle with four flexible wheelsets (86 + 4x33 = 218 coordinates).
  Its rigid counterpart is the published S7e result (V: calibration 0.7 %, closure 1.0 %), so
  only the flexible side has to be simulated;
* the blind test is **cut**, following the cut order in the taskbook (§6) - it is the last item
  before the package rebuild, and it needs two more ten-minute runs.

Everything else - the 30 %-95 % window, the differential construction, the row equilibration, the
Tikhonov lambda, the per-band magnitude error - lives in ``s7e_longwave`` so that a change to the
estimator cannot land in one model and not the other.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parent
REPO = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import s7e_longwave as protocol  # noqa: E402  (one estimator, imported not copied)

WORK = Path(r"F:\velch_tmp\s9i")
CASE = Path(r"F:\velch_tmp\straight\case_straight_axlebox.json")
MODES = REPO / "vehicles" / "modes" / "CRH3C_wheelset_fe.json"
BANDS = (20.0, 40.0)
SPEED = 97.2222
DURATION_S = 2.0
AMPLITUDE_M = 0.10e-3
SHAPE = np.array([0.83, 1.03])
VARIANTS = {"V": ("V",), "D": ("D",), "V+D": ("V", "D")}


def flexible_base() -> dict:
    """The S7e case with four flexible wheelsets, and the modal initial state left at rest."""

    base = json.loads(CASE.read_text(encoding="utf-8"))
    base.pop("initial_state", None)
    for body in base.get("topology", {}).get("bodies", []):
        if body.get("kind") == "axlebox" and isinstance(body.get("axle"), int):
            body["axle"] = body["axle"] - 1
    base["run"]["duration_s"] = DURATION_S
    base["case_id"] = "s9i_flexible"
    base["flexible_wheelset"] = {"source": "file", "file": str(MODES), "axles": [1, 2, 3, 4]}

    # Reviewer D1: the rail templates end at 150 m while this run needs 217.9 m, so the
    # last second of the record was free fall and the differential was not a measurement.
    reach = float(base["run"]["x_start_m"]) + SPEED * DURATION_S + 10.0
    for template in base["rail_templates"]:
        stations = template["stations"]
        last = max(float(station["s_m"]) for station in stations)
        if last < reach:
            clone = dict(max(stations, key=lambda station: float(station["s_m"])))
            clone["s_m"] = 400.0
            clone["id"] = f"{clone.get('id', 'station')}_extended"
            template["stations"] = sorted(stations + [clone], key=lambda station: float(station["s_m"]))
    for template in base["rail_templates"]:
        last = max(float(station["s_m"]) for station in template["stations"])
        if last < reach:
            raise SystemExit(
                f"run leaves the rail station table: reach {reach:.1f} m > last station {last:.1f} m")
    return base


def build_columns(base: dict, length: float) -> dict[str, dict[str, np.ndarray]]:
    """Measure each probe column: one differential pair per band, divided by its amplitude."""
    columns: dict[str, dict[str, np.ndarray]] = {}
    for band in BANDS:
        values = protocol.differential(f"col{band:.0f}", {band: AMPLITUDE_M}, 0.0, base, length)
        columns[str(band)] = {label: np.asarray(value, complex) / AMPLITUDE_M
                              for label, value in values.items()}
        print(f"  band {band:4.0f} m column done", flush=True)
    payload = {
        "bands": list(BANDS),
        "amplitude": AMPLITUDE_M,
        "speed": SPEED,
        "duration": DURATION_S,
        "columns": {key: {label: [[value.real, value.imag] for value in values]
                          for label, values in block.items()}
                    for key, block in columns.items()},
    }
    (WORK / "columns.json").write_text(json.dumps(payload), encoding="utf-8")
    return columns


def load_columns() -> dict[str, dict[str, np.ndarray]]:
    """The per-band probe answers, read from ``columns.json`` instead of re-simulated.

    The first attempt at this script crashed while *printing* the columns (it treated a (2, 2)
    block as a vector), after all four column runs had finished and been written to disk.  The
    cache exists so that an hour of simulation is never spent twice on the same matrix - and so
    that a later change to the estimator cannot silently be graded against a re-simulated H.
    """

    cache = WORK / "columns.json"
    if not cache.exists():
        raise SystemExit(f"no column cache at {cache}: run scripts/s9_inversion.py's column step")
    payload = json.loads(cache.read_text(encoding="utf-8"))
    if (payload.get("bands") != list(BANDS) or payload.get("amplitude") != AMPLITUDE_M
            or payload.get("speed") != SPEED or payload.get("duration") != DURATION_S):
        raise SystemExit(f"{cache} is from another protocol (bands {payload.get('bands')}, "
                         f"amplitude {payload.get('amplitude')})")
    return {key: {label: np.array([complex(real, imaginary) for real, imaginary in values])
                  for label, values in block.items()}
            for key, block in payload["columns"].items()}


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    protocol.WORK = WORK
    protocol.BANDS = BANDS
    protocol.SPEED = SPEED
    protocol.DURATION_S = DURATION_S
    base = flexible_base()
    length = DURATION_S * SPEED + 30.0
    print(f"flexible wheelset, bands {BANDS} m -> "
          + ", ".join(f"{SPEED / band:.2f} Hz" for band in BANDS)
          + f"; {DURATION_S} s = {DURATION_S * SPEED:.0f} m of travel", flush=True)

    started = time.perf_counter()
    if "--columns" in sys.argv or not (WORK / "columns.json").exists():
        columns = build_columns(base, length)
    else:
        columns = load_columns()
    for band in BANDS:
        for label, spec in protocol.CHANNELS.items():
            unit = "m/s^2" if "acc" in spec[0][0] else "m"
            print(f"  band {band:4.0f} m  {label:2s} |H| = "
                  + "  ".join(f"{abs(value):12.4f}" for value in columns[str(band)][label])
                  + f"  ({unit}/m)", flush=True)
    matrix_blocks = {label: np.column_stack([columns[str(band)][label] for band in BANDS])
                     for label in protocol.CHANNELS}

    rng = np.random.default_rng(20261025)
    truth = SHAPE * AMPLITUDE_M
    phase = float(rng.uniform(0.0, 2.0 * np.pi))
    target = protocol.differential("target", dict(zip(BANDS, truth)), phase, base, length)
    print(f"  target done ({time.perf_counter() - started:.0f} s elapsed)", flush=True)

    print("\n  variant  rows  cond      calibration  band errors        recovered mm")
    rows: list[dict[str, object]] = []
    for name, channels in VARIANTS.items():
        matrix = protocol.assemble(matrix_blocks, channels)
        measured = protocol.stack_measured(target, channels)
        cond = float(np.linalg.cond(protocol.balance(matrix, measured)[0]))
        recovered = protocol.solve(matrix, measured, balanced=True)
        calibration = protocol.magnitude_error(recovered, truth)
        bands = protocol.per_band_error(recovered, truth)
        print(f"  {name:7s}  {len(channels) * len(BANDS):4d}  {cond:8.2f}  {calibration:10.1%}  "
              + " / ".join(f"{value:+7.1%}" for value in bands) + "   "
              + " / ".join(f"{abs(value) * 1e3:5.1f}" for value in recovered), flush=True)
        rows.append({"variant": name, "cond": cond, "calibration": calibration, "bands": bands,
                     "recovered_mm": [float(abs(value) * 1e3) for value in recovered],
                     "channels": list(channels)})

    # Closure costs two more runs, so it is measured for the variant that looks best: replaying
    # every variant would double the night's simulation budget for the same information.
    best = min(rows, key=lambda row: float(row["calibration"]))
    channels = tuple(best["channels"])  # type: ignore[arg-type]
    matrix = protocol.assemble(matrix_blocks, channels)
    measured = protocol.stack_measured(target, channels)
    recovered = np.asarray(best["recovered_mm"], dtype=float) * 1e-3
    replay = protocol.differential("replay", dict(zip(BANDS, np.abs(recovered))), phase, base,
                                  length)
    # Compare the *replayed* response with the measured one directly, the way S7e's published
    # 1.0 % was measured.  The first version instead did ``replay_matrix @ ones/len(BANDS)``,
    # i.e. it averaged the two probe columns with a fixed weight of 0.5 and never used the
    # recovered amplitudes at all - that printed 100.4 % for a replay that is within 1.2 %.
    # Magnitudes make the comparison independent of the target phase, so this is well defined.
    reference = np.abs(protocol.stack_measured(target, ("V",)))
    closure = float(np.linalg.norm(np.abs(protocol.stack_measured(replay, ("V",))) - reference)
                    / np.linalg.norm(reference))
    print(f"\n  closure on {best['variant']}: {closure:.2%}")
    best["closure"] = closure

    (WORK / "inversion.json").write_text(json.dumps({
        "truth_mm": [float(value * 1e3) for value in truth],
        "rows": rows, "best": best["variant"],
        "gate": {"calibration": 0.03, "closure": 0.10},
        "rigid_reference": {"calibration": 0.007, "closure": 0.010,
                            "source": "docs/S7E_LONGWAVE_2026-10-24.md"}}, indent=2),
        encoding="utf-8")

    print("\n  gates (taskbook §4): calibration <= 3 %, closure <= 10 %")
    for row in rows:
        calibration_ok = float(row["calibration"]) <= 0.03
        print(f"  {row['variant']:7s} -> calibration "
              + ("ok" if calibration_ok else "FAILED")
              + (f", closure {'ok' if closure <= 0.10 else 'FAILED'}"
                 if row is best else ""))
    print(f"\nwrote {WORK / 'inversion.json'} in {time.perf_counter() - started:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
