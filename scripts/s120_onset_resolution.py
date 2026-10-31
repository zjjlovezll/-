"""Resolve the *station* at which the load split saturates, as a function of bump amplitude.

Round 256 found the observable splits in two above the knee: sigma saturates near 1, so 100 um and 200 um both
read about 62 um, but the station at which saturation starts still moves monotonically
(57.98 -> 57.81 -> 57.58 m).  That is three points, and the output grid at 80 km/h is 11.11 mm, so before the
station can carry the amplitude we have to measure its monotonic range and resolution with more amplitudes.

Pre-registered, before any of these runs exist:

  * ``onset`` never decreases as the amplitude grows;
  * adjacent amplitudes differ by at least one output interval (11.11 mm);
  * the run from 20 um to 120 um does not collapse onto one value.

If the campaign plateaus, the answer is "the station resolves the amplitude only down to some step", and that
is what gets reported -- the gates do not move after the fact.

``onset`` is defined as the first station at which the smoothed blade share reaches ``ONSET_SHARE``.  The peak
station is a worse definition because the split sits on a plateau there and the argmax wanders inside it.

Usage::

    python -X utf8 scripts/s120_onset_resolution.py --build
    python -X utf8 scripts/s120_onset_resolution.py --report
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

import s113_profile_inversion as S  # noqa: E402
import s119_width_aware_inversion as W  # noqa: E402

CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
OUT = ROOT.parent / "scratch" / "s120"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "onset_resolution.json"

SPEED_KMH = 80.0
DURATION_S = 0.6
CENTRE_M = 58.5
SIGMA_M = 1.2
AMPLITUDES_UM = (20.0, 30.0, 40.0, 60.0, 80.0, 120.0)

#: the split must be basically complete before we call it saturated; the same 0.95 the width-aware law used
ONSET_SHARE = 0.95
#: one output frame at 80 km/h with 5e-4 s spacing, in metres
GRID_M = (SPEED_KMH / 3.6) * 5.0e-4


def _variant_path(amplitude_um: float) -> pathlib.Path:
    return OUT / f"one_set_bump{amplitude_um:05.1f}um.json"


def build() -> int:
    """Write one case per amplitude, each a Gaussian on the blade stations only."""
    OUT.mkdir(parents=True, exist_ok=True)
    base = json.loads(CASE.read_text(encoding="utf-8"))
    records = []
    for amplitude_um in AMPLITUDES_UM:
        amplitude_m = amplitude_um * 1e-6
        case = json.loads(json.dumps(base))
        touched = 0
        for template in case["rail_templates"]:
            for body in template.get("bodies", []):
                if body.get("id") != "blade":
                    continue
                for station in body["stations"]:
                    s_m = float(station["s_m"])
                    station["profile"]["z_offset_m"] = float(
                        station["profile"].get("z_offset_m", 0.0)
                        + amplitude_m * float(np.exp(-0.5 * ((s_m - CENTRE_M) / SIGMA_M) ** 2))
                    )
                    touched += 1
        case["case_id"] = f"{case['case_id']}_bump{amplitude_um:05.1f}um"
        case["purpose_detail"] = (
            f"onset-resolution variant: {amplitude_um:.1f} um Gaussian on the blade, {CENTRE_M} m centre, "
            f"{SIGMA_M} m sigma; nothing else changed from the canonical one-set case"
        )
        path = _variant_path(amplitude_um)
        path.write_text(json.dumps(case, indent=1), encoding="utf-8")
        import hashlib

        digest = hashlib.sha256(path.read_bytes()).hexdigest()[:8]
        records.append(
            {"amplitude_um": amplitude_um, "path": str(path), "case_sha256": digest, "stations_touched": touched}
        )
        print(f"{amplitude_um:6.1f} um -> {path.name} ({touched} blade stations, sha {digest})")
    (OUT / "variants.json").write_text(json.dumps(records, indent=1), encoding="utf-8")
    return 0


def _first_above(share: np.ndarray, threshold: float) -> int | None:
    """Index of the first finite sample at or above the threshold, or None if it never gets there."""
    above = np.nonzero(np.isfinite(share) & (share >= threshold))[0]
    return int(above[0]) if above.size else None


def _verdict(deltas: list[float], grid_m: float) -> tuple[bool, bool, bool, str]:
    """Monotone / resolvable / collapsed, from the successive onset deltas (sorted by amplitude)."""
    monotone = all(delta <= 1e-9 for delta in deltas)
    resolvable = all(delta <= -(grid_m - 1e-9) for delta in deltas)
    collapsed = any(abs(delta) < 1e-6 for delta in deltas)
    if monotone and resolvable and not collapsed:
        verdict = "the station carries the amplitude at this resolution"
    else:
        verdict = "the saturation station does NOT resolve these amplitudes at the output grid"
    return monotone, resolvable, collapsed, verdict


def _share_at(run: dict) -> tuple[np.ndarray, np.ndarray]:
    """Blade share versus station for one archived run, smoothed on the 0.20 m window s113 uses."""
    stations = np.asarray(run["station"], dtype=float)
    share = S._smooth(S._split(run), stations, S.SMOOTH_M)
    return stations, share


def report() -> int:
    rows = S._index_rows()
    out = []
    for amplitude_um in AMPLITUDES_UM + (50.0, 100.0, 200.0):
        route = f"one_set_bump{amplitude_um:05.1f}um"
        matches = [
            row
            for row in rows
            if str(row.get("route")) == route
            and abs(float(row.get("speed_kmh", 0.0)) - SPEED_KMH) < 1e-9
            and abs(float(row.get("duration_s", 0.0)) - DURATION_S) < 1e-9
        ]
        if not matches:
            out.append({"amplitude_um": amplitude_um, "status": "no run"})
            continue
        row = matches[-1]
        run = S._load(str(row["run_id"]))
        stations, share = _share_at(run)
        first = _first_above(share, ONSET_SHARE)
        if first is None:
            out.append({"amplitude_um": amplitude_um, "status": "never saturated", "run_id": row["run_id"]})
            continue
        out.append(
            {
                "amplitude_um": amplitude_um,
                "status": "ok",
                "run_id": row["run_id"],
                "onset_station_m": float(stations[first]),
                "peak_station_m": float(stations[int(np.nanargmax(share))]),
                "share_max": float(np.nanmax(share)),
            }
        )

    ok = [row for row in out if row["status"] == "ok"]
    ok.sort(key=lambda row: row["amplitude_um"])
    deltas = [
        (later["onset_station_m"] - earlier["onset_station_m"])
        for earlier, later in zip(ok, ok[1:])
    ]
    monotone, resolvable, collapsed, verdict = _verdict(deltas, GRID_M)

    print(f"{'amp um':>7} {'status':>16} {'onset m':>9} {'peak m':>9} {'share max':>9}  run")
    for row in out:
        if row["status"] == "ok":
            print(
                f"{row['amplitude_um']:7.1f} {'ok':>16} {row['onset_station_m']:9.3f} "
                f"{row['peak_station_m']:9.3f} {row['share_max']:9.3f}  {row['run_id']}"
            )
        else:
            print(f"{row['amplitude_um']:7.1f} {row['status']:>16} {'-':>9} {'-':>9} {'-':>9}  -")
    print()
    print(f"grid per output frame          {GRID_M*1e3:.2f} mm")
    print(f"onset monotone (never later)   {'PASS' if monotone else 'FAIL'}")
    print(f"onset resolvable (>=1 grid)    {'PASS' if resolvable else 'FAIL'}")
    print(f"collapsed onto one station     {'YES' if collapsed else 'no'}")
    print(f"VERDICT: {verdict}")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        json.dumps(
            {
                "speed_kmh": SPEED_KMH,
                "duration_s": DURATION_S,
                "centre_m": CENTRE_M,
                "sigma_m": SIGMA_M,
                "onset_share": ONSET_SHARE,
                "grid_m": GRID_M,
                "rows": out,
                "deltas_m": deltas,
                "monotone": monotone,
                "resolvable": resolvable,
                "collapsed": collapsed,
                "verdict": verdict,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"report -> {REPORT}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="write one case per amplitude")
    parser.add_argument("--report", action="store_true", help="read the archived runs and print the table")
    args = parser.parse_args()
    if args.build:
        return build()
    if args.report:
        return report()
    parser.error("give --build or --report")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
