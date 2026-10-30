"""Read the four-speed campaign back: where does the blade start carrying, and how fast?

The user's 2026-10-31 instruction asks for the lowering surface to be refined by repeated runs at
several speeds, with every run kept so a surrogate can learn from it.  This script is the first
consumer of that archive: it reads `scratch/runs/index.jsonl`, takes the runs of one campaign, and
reports the one observable the design geometry fixes independently of the vehicle -- the station at
which the blade begins to carry load.

Why the station is worth a per-speed table: the geometry says the blade reaches the running surface
(gap = the 65.4661 um static penetration) at 57.733 m and is flush at 58.423 m, both measured from
the sections alone (`scripts/s98_m0_verdict.py`).  A wheel climbing a 6.4 m ramp at 40 km/h follows
that ramp quasi-statically; at 100 km/h it is being thrown up it.  If the first-load station moves
with speed, the lowering inversion needs the speed as an input; if it does not, one calibration
transfers.  Either answer is a result -- what would not be a result is reporting one speed and
calling it the surface.

    PYTHONPATH=src python -X utf8 scripts/s100_speed_campaign.py
    PYTHONPATH=src python -X utf8 scripts/s100_speed_campaign.py --campaign other --write
"""
from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNS = ROOT.parent / "scratch" / "runs"
INDEX = RUNS / "index.jsonl"
OUT = ROOT.parent / "scratch" / "s100"
CASE = ROOT / "vehicles/turnouts/CN60-1100-1_18/cases/straight.json"

#: The blade is said to carry load once it takes this much of the wheel's ~59.68 kN share.
LOAD_THRESHOLDS_N = (1.0e2, 1.0e3, 5.0e3, 1.0e4)
#: From the drawn sections only; recomputed by ``scripts/s98_m0_verdict.py`` at 5 mm resolution.
GEOMETRIC_FIRST_TOUCH_M = 57.733
GEOMETRIC_FLUSH_M = 58.423


def axle_offsets_m() -> list[float]:
    """The axle stations relative to the vehicle origin, as the solver derives them.

    The case does not store them: they follow from ``bogie_half_spacing_m`` and ``wheelbase_m``
    (``+a+b, +a-b, -a+b, -a-b``), so they are read through the loader rather than re-derived here.
    """
    from velch.vehicle import load_vehicle_case

    return [float(value) for value in load_vehicle_case(CASE).vehicle.axle_offsets_m]


def campaign_runs(campaign: str) -> list[dict]:
    if not INDEX.exists():
        raise SystemExit(f"no archive yet ({INDEX})")
    rows = [json.loads(line) for line in INDEX.read_text(encoding="utf-8").splitlines() if line.strip()]
    picked = []
    for row in rows:
        meta_path = pathlib.Path(row["path"]) / "meta.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("notes", {}).get("campaign") != campaign:
            continue
        picked.append({**row, "meta": meta})
    picked.sort(key=lambda item: float(item["speed_kmh"]))
    return picked


def analyse(run: dict, offsets: list[float]) -> dict:
    directory = pathlib.Path(run["path"])
    arrays = np.load(directory / "series.npz")
    meta = run["meta"]
    labels = list(meta.get("body_labels") or [])
    speed = float(meta["speed_m_s"])
    x_start = float(meta["x_start_m"])

    blade_columns = [index for index, label in enumerate(labels) if label.endswith("/blade")]
    stock_columns = [index for index, label in enumerate(labels) if label.endswith("/stock")]
    if not blade_columns:
        raise SystemExit(f"{run['run_id']}: the archive has no blade column ({labels})")
    body = np.asarray(arrays["body_normal_force_n"], dtype=float)
    blade = body[:, blade_columns].sum(axis=1)
    stock = body[:, stock_columns].sum(axis=1)
    times = np.asarray(arrays["times"], dtype=float)
    station = x_start + speed * times + offsets[0]

    # Per axle, so a single axle's entry into the blade region cannot be mistaken for the whole wheel.
    per_axle = {}
    for axle in range(len(offsets)):
        columns = [index for index, label in enumerate(labels)
                   if label.startswith(f"axle{axle + 1}_right") and label.endswith("/blade")]
        if not columns:
            continue
        force = body[:, columns].sum(axis=1)
        per_axle[f"axle{axle + 1}"] = _first_crossing(force, x_start + speed * times + offsets[axle])

    first = {f"{threshold:g}": _first_crossing(blade, station) for threshold in LOAD_THRESHOLDS_N}
    peak = float(blade.max()) if blade.size else 0.0
    peak_at = float(station[int(np.argmax(blade))]) if blade.size else float("nan")
    lead = [index for index, label in enumerate(labels)
            if label.startswith("axle1_right") and label.endswith("/blade")]
    lead_force = body[:, lead].sum(axis=1) if lead else np.zeros(0)
    lead_peak = float(lead_force.max()) if lead_force.size else 0.0
    lead_peak_at = float(station[int(np.argmax(lead_force))]) if lead_force.size else float("nan")
    return {
        "run_id": run["run_id"],
        "speed_kmh": float(run["speed_kmh"]),
        "frames": int(station.size),
        "first_load_m": first,
        "per_axle_1kN_m": {key: value for key, value in per_axle.items()},
        "blade_peak_n": peak,
        "blade_peak_at_m": peak_at,
        "axle1_peak_n": lead_peak,
        "axle1_peak_at_m": lead_peak_at,
        "stock_at_blade_peak_n": float(stock[int(np.argmax(blade))]) if blade.size else float("nan"),
        "blade_end_n": float(blade[-1]) if blade.size else float("nan"),
        "front_axle_end_m": float(station[-1]),
        "gates": meta.get("gates", {}),
        "wall_s": float(meta.get("wall_s", 0.0)),
    }


def _first_crossing(force: np.ndarray, station: np.ndarray) -> float | None:
    index = np.nonzero(force > 0.0)[0]
    return float(station[int(index[0])]) if index.size else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--campaign", default="blade-lowering-2026-10-31")
    ap.add_argument("--threshold", type=float, default=1.0e3,
                    help="N, the level that counts as 'carrying' in the printed table")
    ap.add_argument("--write", action="store_true", help="write scratch/s100/campaign.json")
    args = ap.parse_args()

    offsets = axle_offsets_m()
    runs = campaign_runs(args.campaign)
    if not runs:
        raise SystemExit(f"no archived run carries campaign={args.campaign!r}")

    results = [analyse(run, offsets) for run in runs]
    key = f"{args.threshold:g}"
    print(f"campaign {args.campaign}   geometry: first touch {GEOMETRIC_FIRST_TOUCH_M:.3f} m, "
          f"flush {GEOMETRIC_FLUSH_M:.3f} m")
    print("all forces below are per axle unless the column says 'sum'")
    print(f"{'speed':>7}{'sample mm':>10}{'lead first':>11}{'offset':>8}"
          f"{'axle1 peak kN':>14}{'at m':>8}{'axle2 first':>12}")
    for row in results:
        first_1k = row["first_load_m"].get("1000", 0.0)
        offset = (first_1k - GEOMETRIC_FIRST_TOUCH_M) if first_1k else float("nan")
        sample_mm = row["speed_kmh"] / 3.6 * 5e-4 * 1e3
        print(f"{row['speed_kmh']:>7.1f}{sample_mm:>10.2f}{_fmt(first_1k):>11}{offset:>8.3f}"
              f"{row['axle1_peak_n'] / 1e3:>14.2f}{row['axle1_peak_at_m']:>8.3f}"
              f"{_fmt(row['per_axle_1kN_m'].get('axle2')):>12}")
    print("per-axle first load above 1 kN (m):")
    for row in results:
        print(f"  {row['speed_kmh']:>6.1f} km/h  " + "  ".join(
            f"{axle} {_fmt(value)}" for axle, value in sorted(row["per_axle_1kN_m"].items())))
    spread = [row["first_load_m"].get("1000") for row in results if row["first_load_m"].get("1000")]
    if len(spread) > 1:
        print(f"spread of the leading first-load station over "
              f"{results[0]['speed_kmh']:.0f}-{results[-1]['speed_kmh']:.0f} km/h: "
              f"{(max(spread) - min(spread)) * 1e3:.1f} mm")
    if args.write:
        OUT.mkdir(parents=True, exist_ok=True)
        payload = {"campaign": args.campaign, "geometry": {
            "first_touch_m": GEOMETRIC_FIRST_TOUCH_M, "flush_m": GEOMETRIC_FLUSH_M,
            "static_penetration_um": 65.4661},
            "runs": results}
        (OUT / "campaign.json").write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
                                           encoding="utf-8")
        print(f"data -> {OUT / 'campaign.json'}")
    return 0


def _fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.3f}"


if __name__ == "__main__":
    raise SystemExit(main())
