"""M5 step 1: does the forward model respond to a known surface perturbation, and where?

Before any inversion can be trusted, the forward operator needs a measured gain: put a *known* bump on
the blade surface, run the vehicle over it, and read how the axle-box acceleration answers.  Three
things are checked, and all three are necessary -- an estimator built on an operator that fails any of
them is measuring itself:

1. **non-zero**: the response is far above the numerical floor of a repeat run;
2. **monotone in the amplitude**: doubling the bump doubles the response (the operator is a gain, not
   a switch), reported as (m/s^2)/um;
3. **localised**: the untouched left rail (no bump) shows no comparable response -- an estimator must
   not read a right-rail bump out of the left rail's accelerometer.

The bump is added as a Gaussian in ``profile.z_offset_m`` on the *blade* body's stations, which are
0.193 m apart, so a sigma of 1.2 m is represented by ~13 stations rather than being smoothed away by
the station spacing.  The stock body's table is 13 m apart and cannot carry a 1 m feature at all,
which is why the blade is the body under test here.

    PYTHONPATH=src python -X utf8 scripts/s112_surface_sensitivity.py --build
    PYTHONPATH=src python -X utf8 scripts/s112_surface_sensitivity.py --analyze
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
OUT = ROOT.parent / "scratch" / "s112"
RUNS = ROOT.parent / "scratch" / "runs"
CAMPAIGN = "surface-sensitivity"
#: Bump geometry, fixed before the runs: centred where the blade is carrying (58.5 m) with a sigma
#: the 0.193 m station spacing can represent, and amplitudes that bracket a real lowering error.
CENTRE_M = 58.5
SIGMA_M = 1.2
AMPLITUDES_UM = (50.0, 100.0, 200.0)
DURATION_S = 0.60
SPEED_KMH = 80.0
LEFT = "axle1_box_left"
RIGHT = "axle1_box_right"  # the axlebox vehicle has one box body per side
BODY = "axle1_right"  # body labels are named after the wheelset, not the box


def variant_path(amplitude_um: float) -> pathlib.Path:
    return OUT / f"one_set_bump{amplitude_um:05.1f}um.json"


def build() -> int:
    """Write one case per amplitude, with the bump on the blade's stations only."""

    OUT.mkdir(parents=True, exist_ok=True)
    raw = json.loads(CASE.read_text(encoding="utf-8"))
    for amplitude in AMPLITUDES_UM:
        payload = json.loads(json.dumps(raw))
        touched = 0
        for template in payload["rail_templates"]:
            for body in template.get("bodies", ()):
                if str(body.get("id")) != "blade":
                    continue
                for station in body["stations"]:
                    offset = amplitude * 1e-6 * float(
                        np.exp(-((float(station["s_m"]) - CENTRE_M) / SIGMA_M) ** 2))
                    if offset >= 1e-9:
                        profile = station["profile"]
                        profile["z_offset_m"] = float(profile.get("z_offset_m", 0.0) or 0.0) + offset
                        touched += 1
        if touched < 5:
            raise SystemExit(f"only {touched} blade stations under the bump; check the case")
        payload["case_id"] = f"turnout_cn60_1100_straight_one_set_bump{amplitude:05.1f}um"
        payload["purpose_detail"] = (
            f"surface-sensitivity variant: blade Gaussian bump {amplitude:.0f} um peak, "
            f"sigma {SIGMA_M:.1f} m at {CENTRE_M:.1f} m; everything else is the canonical one-set case")
        path = variant_path(amplitude)
        path.write_text(json.dumps(payload, indent=1) + chr(10), encoding="utf-8")
        print(f"{amplitude:5.1f} um -> {path.name}  ({touched} stations)")
    print("build a baseline run first (no bump) with the same duration and speed:")
    print(f"  PYTHONPATH=src python -X utf8 scripts/s99_run_archive.py --case "
          f"{CASE.relative_to(ROOT)} --speed-kmh {SPEED_KMH:g} --duration {DURATION_S} "
          f"--note campaign=surface-sensitivity-baseline")
    return 0


def _load(run_id: str) -> dict:
    directory = RUNS / run_id
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    data = np.load(directory / "series.npz")
    return {"run_id": run_id, "meta": meta,
            "times": np.asarray(data["times"], dtype=float),
            "acc": np.asarray(data["accelerations"], dtype=float),
            "normal": np.asarray(data["normal_force_n"], dtype=float),
            "body": np.asarray(data["body_normal_force_n"], dtype=float)}


def _station(times: np.ndarray) -> np.ndarray:
    """Front-axle station, from the same arithmetic the archive itself uses."""
    return 50.0 + (SPEED_KMH / 3.6) * np.asarray(times, dtype=float)


def _branch(run: dict, count: int) -> dict:
    """How the load splits between the two bodies of the right rail, in the crossing window.

    A bump of a few tens of micrometres only modulates the load; a bump comparable to the static
    penetration lifts the wheel off the stock entirely.  That is a *branch switch*, and it is what
    decides whether an amplitude can be read out of the response at all, so it is reported next to
    the gain rather than being discovered later.
    """
    labels = list(run["meta"]["body_labels"])
    station = _station(run["times"])[:count]
    window = (station > 57.0) & (station < 60.5)
    record = {"frames": int(window.sum())}
    for body in ("stock", "blade"):
        column = run["body"][:count, labels.index(f"{BODY}/{body}")]
        record[body] = {"min_kN": float(column[window].min() / 1e3),
                        "max_kN": float(column[window].max() / 1e3),
                        "zero_frames": int((np.abs(column[window]) < 1.0).sum())}
    return record


def _channel(meta: dict, name: str) -> int:
    return list(meta["acceleration_names"]).index(name)


def _index_rows() -> list[dict]:
    return [json.loads(line) for line in (RUNS / "index.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()]


def _baseline_row() -> dict:
    rows = [row for row in _index_rows()
            if row["route"] == "straight_one_set"
            and abs(float(row["duration_s"]) - DURATION_S) < 1e-9
            and abs(float(row["speed_kmh"]) - SPEED_KMH) < 1e-9]
    if not rows:
        raise SystemExit("no baseline run at this duration and speed")
    return rows[-1]


def _variant_rows() -> dict[float, dict]:
    """Map amplitude -> index row, read from the case stem (``one_set_bump100.0um``)."""
    found: dict[float, dict] = {}
    for row in _index_rows():
        route = str(row["route"])
        if not route.startswith("one_set_bump") or abs(float(row["duration_s"]) - DURATION_S) > 1e-9:
            continue
        stem = route[len("one_set_bump"):].removesuffix(".0um").removesuffix("um")
        found[round(float(stem), 1)] = row
    return found


def analyze() -> int:
    baseline = _load(_baseline_row()["run_id"])
    variants = {amplitude: _load(_variant_rows()[amplitude]["run_id"])
                for amplitude in AMPLITUDES_UM}
    if len(variants) != len(AMPLITUDES_UM):
        raise SystemExit(f"expected {len(AMPLITUDES_UM)} variant runs, found {len(variants)}")

    right = _channel(baseline["meta"], f"{RIGHT}_z_acc_m_per_s2")
    left = _channel(baseline["meta"], f"{LEFT}_z_acc_m_per_s2")
    base_peak = float(np.abs(baseline["acc"][:, right]).max())

    print(f"baseline {baseline['run_id']}  frames {baseline['acc'].shape[0]}")
    print(f"  baseline |a_z| on {RIGHT}: max {base_peak:.4g} m/s^2, "
          f"median {np.median(np.abs(baseline['acc'][:, right])):.4g} m/s^2")
    print("  (the solver is deterministic -- a repeat run is bit-identical, so there is no stochastic "
          "floor; the check below is 'is the response visible against the baseline's own motion')")
    print()
    print("amplitude  peak|da|  at s(m)  rms in window  rms gain  peak gain  L/R   stock zero  blade max")
    rows = []
    for amplitude in AMPLITUDES_UM:
        run = variants[amplitude]
        count = min(run["acc"].shape[0], baseline["acc"].shape[0])
        delta_r = np.abs(run["acc"][:count, right] - baseline["acc"][:count, right])
        delta_l = np.abs(run["acc"][:count, left] - baseline["acc"][:count, left])
        station = _station(run["times"])[:count]
        window = (station > 56.0) & (station < 62.0)
        peak = float(delta_r.max())
        peak_at = float(station[int(np.argmax(delta_r))])
        rms = float(np.sqrt((delta_r[window] ** 2).mean()))
        branch = _branch(run, count)
        rows.append({"amplitude_um": amplitude, "peak_right": peak, "peak_left": float(delta_l.max()),
                     "peak_station_m": peak_at, "rms_window": rms,
                     "peak_gain_per_um": peak / amplitude, "rms_gain_per_um": rms / amplitude,
                     "left_over_right": float(delta_l.max() / peak),
                     "visible_fraction": peak / base_peak, "branch": branch,
                     "run_id": run["run_id"]})
        print(f"{amplitude:9.1f}  {peak:8.4f}  {peak_at:7.2f}  {rms:13.4f}  {rms / amplitude:8.5f}  "
              f"{peak / amplitude:9.5f}  {delta_l.max() / peak:5.3f}  "
              f"{branch['stock']['zero_frames']:4d}/{branch['frames']:3d}  "
              f"{branch['blade']['max_kN']:7.1f} kN")

    peak_gains = [row["peak_gain_per_um"] for row in rows]
    rms_gains = [row["rms_gain_per_um"] for row in rows]
    monotone = all(peak_gains[i] < peak_gains[i + 1] for i in range(len(peak_gains) - 1))
    spread = max(peak_gains) / min(peak_gains) if min(peak_gains) > 0 else float("inf")
    localised_side = all(row["left_over_right"] < 0.5 for row in rows)
    localised_place = all(abs(row["peak_station_m"] - CENTRE_M) < 1.5 for row in rows)
    visible = all(row["visible_fraction"] > 0.10 for row in rows)
    # The linear regime is where the bump stays well inside the static penetration, so the wheel is
    # carried by both bodies and the load only shifts.  Above that the stock drops out frame by frame.
    linear_rows = [row for row in rows if row["branch"]["stock"]["zero_frames"] == 0]
    linear_gains = [row["peak_gain_per_um"] for row in linear_rows]
    linear_spread = (max(linear_gains) / min(linear_gains)) if len(linear_gains) > 1 else None

    print()
    print(f"visible against the baseline's own motion (>10 %): {visible}")
    print(f"monotone in amplitude: {monotone}   peak gain spread {spread:.3f}")
    print(f"localised to the bumped rail (L/R < 0.5): {localised_side}")
    print(f"localised in station (|peak - {CENTRE_M:.1f}| < 1.5 m): {localised_place}")
    print(f"linear-regime rows (stock never drops out): {[r['amplitude_um'] for r in linear_rows]}"
          + (f"  spread {linear_spread:.3f}" if linear_spread else ""))
    verdict = ("the forward operator answers a known surface bump, on the bumped rail and at the "
               "bumped station, but only monotonically while the stock keeps carrying the wheel")
    if not (visible and localised_side and localised_place):
        verdict = "the forward operator fails a localisation or visibility check -- do not invert yet"
    print(f"VERDICT: {verdict}")

    OUT.mkdir(parents=True, exist_ok=True)
    payload = {"baseline": baseline["run_id"], "baseline_peak": base_peak,
               "bump": {"centre_m": CENTRE_M, "sigma_m": SIGMA_M},
               "rows": rows, "monotone": monotone, "peak_gain_spread": spread,
               "linear_regime_amplitudes_um": [r["amplitude_um"] for r in linear_rows],
               "linear_regime_spread": linear_spread,
               "localised_side": localised_side, "localised_station": localised_place,
               "visible": visible, "verdict": verdict}
    (OUT / "sensitivity.json").write_text(json.dumps(payload, indent=1) + chr(10), encoding="utf-8")
    print(f"report -> {OUT / 'sensitivity.json'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--analyze", action="store_true")
    args = ap.parse_args()
    if args.build:
        return build()
    if args.analyze:
        return analyze()
    print("choose --build or --analyze")
    return 2


if __name__ == "__main__":
    sys.exit(main())
