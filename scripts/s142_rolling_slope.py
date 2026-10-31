"""Does a raise respond the same way when the wheel rolls over it as when the axle stands on it?

Round 284 showed the *seated* split equals the *rolling* split at ten stations (median 0.0022).  That proves
the zero point, not the response: the seated sensitivity (+0.0038 .. +0.0047 share per um) has never been
compared with the slope the rolling run actually produces.  If they differ, a per-station seating campaign is
a table of the right numbers with the wrong derivative -- and the inversion needs the derivative.

Design
    six stations (58.0, 58.5, 59.0, 60.0, 61.0, 62.0) x two raises (50, 100 um)
    the raise is the same single-station geometry s141 seated on, so the two readings are the same object
    reference: the un-bumped archived run (share at each station, raise = 0)

    R4  rolling slope vs seated slope: |difference| <= 40 % of the seated slope at every station
    R5  the rolling share must rise with the raise at every station (same sign as seated)
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import s113_profile_inversion as INV          # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
OUT = ROOT.parent / "scratch" / "s142"
REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "rolling_slope.json"
SEATED = ROOT / "reports" / "load_split_inversion_2026-10-31" / "solver_calibration.json"

# the blade station table ends at 60.962 m, so a raise asked for at 61 or 62 m lands on that same last
# station and would alias two probes onto one object; only stations with their own profile are used.
STATIONS = (58.0, 58.5, 59.0, 60.0)
RAISES_UM = (50.0, 100.0)
SPEED_KMH = 80.0
DURATION_S = 0.6
SLOPE_TOLERANCE = 0.40


def route_of(station_m: float, raise_um: float) -> str:
    return f"one_set_slope_s{station_m:05.2f}_r{raise_um:03.0f}um"


def build() -> list[dict]:
    raw_text = CASE.read_text(encoding="utf-8")
    variants = []
    for station in STATIONS:
        for raise_um in RAISES_UM:
            raw = json.loads(raw_text)
            hit = None
            for template in raw["rail_templates"]:
                for body in template.get("bodies") or []:
                    if body["id"] != "blade":
                        continue
                    stations = body["stations"]
                    best = min(range(len(stations)),
                               key=lambda k: abs(float(stations[k]["s_m"]) - station))
                    profile = stations[best]["profile"]
                    profile["z_offset_m"] = float(profile.get("z_offset_m", 0.0)) + raise_um * 1e-6
                    hit = float(stations[best]["s_m"])
            raw["case_id"] = route_of(station, raise_um)
            raw["purpose_detail"] = ("rolling-slope probe: one blade station raised, full run"
                                    f" (station {station:.2f} m, raise {raise_um:.0f} um)")
            raw.pop("path", None)
            raw.pop("initial_state", None)
            OUT.mkdir(parents=True, exist_ok=True)
            path = OUT / f"{route_of(station, raise_um)}.json"
            path.write_text(json.dumps(raw, indent=1), encoding="utf-8")
            variants.append({
                "station_m": station,
                "raise_um": raise_um,
                "profile_station_m": hit,
                "route": route_of(station, raise_um),
                "path": str(path),
            })
            print(f"built {path.name}  (profile station {hit:.3f})")
    (OUT / "variants.json").write_text(json.dumps(variants, indent=1), encoding="utf-8")
    return variants


def run(variants: list[dict]) -> None:
    archive = ROOT / "scripts" / "s99_run_archive.py"
    for index, variant in enumerate(variants, 1):
        print(f"[{index}/{len(variants)}] {variant['route']}", flush=True)
        command = [
            sys.executable, "-X", "utf8", str(archive),
            "--case", variant["path"],
            "--speed-kmh", str(SPEED_KMH),
            "--duration", str(DURATION_S),
            "--note", "campaign=rolling-slope",
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        tail = (result.stdout or "").strip().splitlines()[-1:] or [""]
        print(f"   {tail[0]}", flush=True)
        if result.returncode != 0:
            print(f"   FAILED\n{(result.stdout or '')[-500:]}\n{(result.stderr or '')[-800:]}", flush=True)


def share_at(run_id: str, station_m: float) -> float:
    run = INV._load(run_id)
    table = run["station"]
    share = INV._smooth(INV._split(run), table, INV.SMOOTH_M)
    index = int(np.argmin(np.abs(table - station_m)))
    return float(share[index])


def report(variants: list[dict], write: bool) -> int:
    seated = json.loads(SEATED.read_text(encoding="utf-8"))
    seated_rows = {(round(row["station_m"], 2), round(row["raise_um"])): row["share_seated"]
                   for row in seated["rows"]}

    archived = {row["route"] for row in INV._index_rows()}
    rows = []
    for station, raise_um, variant in _pairs(variants):
        if variant["route"] not in archived:
            print(f"skip {variant['route']} (not archived yet)")
            continue
        run_id = INV._run_id(variant["route"])
        rolled = share_at(run_id, station)
        reference = share_at(INV._run_id("straight_one_set"), station)
        rows.append({
            "station_m": station,
            "raise_um": raise_um,
            "run_id": run_id,
            "share_rolling": rolled,
            "share_rolling_null": reference,
            "share_seated": seated_rows.get((round(station, 2), round(raise_um))),
            "route": variant["route"],
        })
        print(f"s {station:6.2f}  raise {raise_um:5.0f} um   rolling {rolled:.4f} "
              f"(null {reference:.4f})   seated {rows[-1]['share_seated']}")

    comparisons = []
    for station in sorted({row["station_m"] for row in rows}):
        near = [row for row in rows if row["station_m"] == station]
        if len(near) < 2:
            continue
        raise_top = max(near, key=lambda row: row["raise_um"])
        seated_delta = (raise_top["share_seated"] or 0.0) - (seated_rows.get((round(station, 2), 0)) or 0.0)
        rolling_delta = raise_top["share_rolling"] - raise_top["share_rolling_null"]
        seated_slope = seated_delta / (raise_top["raise_um"] * 1e-6)
        rolling_slope = rolling_delta / (raise_top["raise_um"] * 1e-6)
        ratio = (rolling_slope / seated_slope) if seated_slope else float("nan")
        comparisons.append({
            "station_m": station,
            "seated_slope_per_m": float(seated_slope),
            "rolling_slope_per_m": float(rolling_slope),
            "ratio": float(ratio),
        })
        print(f"[R4] s {station:6.2f}  seated {seated_slope:+10.1f}  rolling {rolling_slope:+10.1f}  "
              f"ratio {ratio:+.2f}")

    r4 = all(abs(item["ratio"] - 1.0) <= SLOPE_TOLERANCE for item in comparisons)
    r5 = all(item["rolling_slope_per_m"] > 0 for item in comparisons)
    verdict = (
        "the rolling slope is the seated slope: a per-station seating table can carry the derivative"
        if (r4 and r5)
        else "the seated slope is not the rolling slope: a seating table has the right zeros and the wrong "
             "derivative"
    )
    print(f"\nR4 slopes agree within {SLOPE_TOLERANCE:.0%}: {'PASS' if r4 else 'FAIL'}")
    print(f"R5 rolling slope positive at every station: {'PASS' if r5 else 'FAIL'}")
    print(f"VERDICT: {verdict}")

    if write:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps({
            "pre_registered": {"stations": list(STATIONS), "raises_um": list(RAISES_UM),
                               "slope_tolerance": SLOPE_TOLERANCE},
            "rows": rows,
            "comparisons": comparisons,
            "r4": r4,
            "r5": r5,
            "verdict": verdict,
        }, indent=1), encoding="utf-8")
        print(f"report -> {REPORT}")
    return 0


def _pairs(variants: list[dict]):
    for variant in variants:
        yield variant["station_m"], variant["raise_um"], variant


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)

    variants_path = OUT / "variants.json"
    if args.build:
        variants = build()
    elif variants_path.exists():
        variants = json.loads(variants_path.read_text(encoding="utf-8"))
    else:
        variants = []
    if args.run:
        run(variants)
    if args.report:
        return report(variants, args.write)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
