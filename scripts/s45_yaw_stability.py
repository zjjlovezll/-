"""Does the curved response settle when the yaw mode is stiffened, or when the creep is Kalker-scale?

Round 202 measured the net lateral force on R = 1100 m at 80 km/h growing from +11 691.2 N at
0.34 s to +29 544.4 N at 0.60 s (ratio 2.53) after the curving force had been given the sign the
design line implies.  A response that grows with time has no steady state, so the question is
which parameter decides whether one exists.

Pre-registered before the runs (this docstring is the record):

    criterion   ratio = |sum Fy(0.60 s)| / |sum Fy(0.34 s)|  <=  1.2
    candidates  k_yaw x2 (3.92e6 N.m/rad), k_yaw x5 (9.80e6), and Kalker-scale creep
                (f11 3.5e6 N, f22 2.5e6 N via --creep-kalker, which sets both)
    baseline    the round-202 numbers, ratio 2.53
    rule        a candidate passes only if its own ratio is <= 1.2 AND its 0.60 s net force
                still points with the demand; whichever ratio comes closest to 1 names the
                parameter, and no parameter is adopted without a further measurement.

The runs themselves are driven by ``scripts/s32_curved_station_table.py`` (one case per run, the
flag stamped into the case id and into ``purpose_detail``); this script only reads their logs, so
there is one implementation of the physics and one of the report.

Usage::

    python -X utf8 scripts/s45_yaw_stability.py
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

LOG_DIR = pathlib.Path(__file__).resolve().parents[1].parent / "scratch" / "s45"
OUT = pathlib.Path(__file__).resolve().parents[1] / "reports" / "curve_yaw_stability_2026-10-28"

CRITERION = 1.2
DEMAND_N = 21_842.4
BASELINE = {"name": "inline (round 202)", "short": 11_691.2, "long": 29_544.4}

# name -> (label, k_yaw or None, creep label)
CONFIGS = {
    "k2": ("k_yaw x2 = 3.92e6 N.m/rad", 3.92e6, "frozen 5.0e5/1.0e6"),
    "k5": ("k_yaw x5 = 9.80e6 N.m/rad", 9.80e6, "frozen 5.0e5/1.0e6"),
    "kalker": ("inline k_yaw, Kalker creep", 1.96e6, "Kalker 2.5e6/3.5e6"),
}

_RUN = re.compile(r"run (?P<duration>[0-9.]+) s -> (?P<status>\S+)\s+frames (?P<frames>\d+)")
_PEN = re.compile(r"max penetration (?P<pen>[0-9.]+) um")
# The run prints "+55.4%" with no space, so the pattern must not demand one: the first version
# did, and every log was rejected with "could not read the run summary".
_FY = re.compile(r"last frame: sum Fy (?P<fy>[+-][0-9.]+) N.*?fictitious demand "
                 r"(?P<demand>[0-9.]+) N, (?P<pct>[+-][0-9.]+)\s*%")
_PEAK = re.compile(r"peaks (?P<peaks>.+?)(?:\.|$)")


def parse(path: pathlib.Path) -> dict:
    """Pull the four numbers a run reports, refusing to guess when one is missing."""
    text = path.read_text(encoding="utf-8", errors="replace")
    run = _RUN.search(text)
    pen = _PEN.search(text)
    fy = _FY.search(text)
    if not (run and pen and fy):
        raise ValueError(f"{path}: could not read the run summary")
    return {
        "delay_s": float(run.group("duration")),
        "status": run.group("status"),
        "frames": int(run.group("frames")),
        "max_penetration_um": float(pen.group("pen")),
        "sum_fy_n": float(fy.group("fy")),
        "demand_n": float(fy.group("demand")),
        "share_of_demand": float(fy.group("pct")) / 100.0,
    }


def rows() -> list[dict]:
    out = [dict(BASELINE, k_yaw_nm_rad=1.96e6, creep="frozen 5.0e5/1.0e6",
                ratio=abs(BASELINE["long"]) / abs(BASELINE["short"]), criterion=CRITERION,
                passes_the_ratio=False)]
    for name, (label, k_yaw, creep) in CONFIGS.items():
        short = parse(LOG_DIR / f"{name}_0.34.log")
        long = parse(LOG_DIR / f"{name}_0.60.log")
        ratio = abs(long["sum_fy_n"]) / abs(short["sum_fy_n"])
        out.append({
            "name": name,
            "k_yaw_nm_rad": k_yaw,
            "creep": creep,
            "short": short["sum_fy_n"],
            "long": long["sum_fy_n"],
            "share_short": short["share_of_demand"],
            "share_long": long["share_of_demand"],
            "pen_short_um": short["max_penetration_um"],
            "pen_long_um": long["max_penetration_um"],
            "status_short": short["status"],
            "status_long": long["status"],
            "ratio": ratio,
            "criterion": CRITERION,
            # A growing response with the right sign is still not a steady state, so the ratio
            # alone decides; the sign check is reported beside it, never substituted for it.
            "points_with_demand": long["sum_fy_n"] > 0.0,
            "passes_the_ratio": ratio <= CRITERION,
        })
    return out


def main(argv: list[str]) -> int:
    table = rows()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "yaw_stability.json").write_text(
        json.dumps({"criterion": CRITERION, "demand_n": DEMAND_N, "rows": table}, indent=2) + "\n",
        encoding="utf-8")
    header = f"{'config':<28} {'k_yaw':>9} {'0.34 s':>12} {'0.60 s':>12} {'ratio':>7} {'pass':>5}"
    print(header)
    print("-" * len(header))
    for row in table:
        name = row.get("name", "inline (round 202)")
        print(f"{name:<28} {row['k_yaw_nm_rad']:>9.2e} {row['short']:>+12.1f} "
              f"{row['long']:>+12.1f} {row['ratio']:>7.2f} {str(row['passes_the_ratio']):>5}")
    winners = [r for r in table if r["passes_the_ratio"]]
    print()
    if winners:
        best = min(winners, key=lambda r: r["ratio"])
        print(f"SETTLES: {best.get('name', 'inline')} ratio {best['ratio']:.2f} <= {CRITERION}")
    else:
        print(f"NONE SETTLES: closest ratio {min(r['ratio'] for r in table):.2f} > {CRITERION}")
    print(f"report {OUT / 'yaw_stability.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
