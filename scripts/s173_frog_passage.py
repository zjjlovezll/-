"""Cross from the switch blade into the frog and read the transfer per body.

Every archive in this repository stops at or before 70 m.  The frog body spans
103.280-116.440 m, so no run has ever asked who carries the wheel between the
wing rail (the tail of the ``blade`` body, which ends at 104.419 m) and the
long point rail.  This script runs the passage once and reads, frame by frame,
the normal force on each *body* of the right-hand rail -- not the rail total,
which cannot tell the two apart.

The question it answers, in order:

1. at which mileage does the ``frog`` body first carry the wheel (>= 1 kN for
   three consecutive frames), and at which mileage does the ``blade`` body
   last carry it at or above 5 % of the axle load;
2. does the sum over bodies equal the rail total, frame by frame (the identity
   that says the readout is not double counting);
3. does the run stay inside its gates while crossing.

Nothing here changes the physics: one setup, one speed, one run.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from velch import setup as setup_module  # noqa: E402
from velch.vehicle_solver import simulate_vehicle  # noqa: E402

RAIL_ID = "axle1_right"
AXLE_OFFSET_M = 10.0
SETUP = ROOT / "setups" / "one_set_passage.json"
REPORT = ROOT / "reports" / "frog_passage_2026-11-01" / "passage.json"

FIRST_LOAD_KN = 1.0
RELEASE_SHARE = 0.05
CONSECUTIVE_FRAMES = 3


def _body_name(body_id: object) -> str:
    """The last colon-separated token, so ``right:frog`` and ``frog`` agree."""

    return str(body_id).split(":")[-1]


def per_body_series(result) -> dict[str, list[float]]:
    """Normal force for each body of one rail, frame by frame, in frame order."""

    series: dict[str, list[float]] = {}
    frames = len(result.body_contacts or ())
    for frame_index in range(frames):
        contacts = result.body_contacts[frame_index]
        ids = result.body_ids[frame_index]
        for name, response in zip(ids.get(RAIL_ID, ()), contacts.get(RAIL_ID, ())):
            series.setdefault(_body_name(name), []).append(float(response.normal_force_n))
    return series


def series_matrix(series: dict[str, list[float]], frames: int) -> dict[str, np.ndarray]:
    """Pad every body to the full frame count (a body absent in a frame is zero)."""

    out: dict[str, np.ndarray] = {}
    for name, values in series.items():
        array = np.zeros(frames, dtype=float)
        array[: len(values)] = values[:frames]
        out[name] = array
    return out


def first_sustained(force_kn: np.ndarray, threshold_kn: float, frames: int = CONSECUTIVE_FRAMES) -> int | None:
    """Index of the first run of ``frames`` consecutive samples above ``threshold_kn``."""

    run = 0
    for index, flag in enumerate(force_kn >= threshold_kn):
        run = run + 1 if flag else 0
        if run >= frames:
            return index - frames + 1
    return None


def main(argv: list[str] | None = None) -> int:
    import argparse

    global REPORT

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--setup", default=str(SETUP), help="setup json to resolve (default: the passage)")
    parser.add_argument("--duration", type=float, default=None, help="override duration.s")
    parser.add_argument("--report", default=str(REPORT), help="where to write the json")
    args = parser.parse_args(argv)
    REPORT = Path(args.report)
    started = time.perf_counter()
    overrides = () if args.duration is None else [f"duration.s={args.duration}"]
    resolved = setup_module.resolve(setup_module.load_setup(Path(args.setup)), overrides)
    print(setup_module.render_table(resolved.table))
    case = resolved.case
    travel = float(case.vehicle.travel_speed_m_s)
    x_start = float(case.run.x_start_m)

    result = simulate_vehicle(case)
    elapsed = time.perf_counter() - started

    times = np.asarray(result.times_s, dtype=float)
    frames = int(times.size)
    stations = x_start + AXLE_OFFSET_M + travel * times

    series = per_body_series(result)
    arrays = series_matrix(series, frames)
    if not arrays:
        print("no per-body contacts were captured -- result.body_contacts is empty", file=sys.stderr)
        return 2

    rail_total = np.zeros(frames, dtype=float)
    for frame_index, contacts in enumerate(result.body_contacts or ()):
        for response in contacts.get(RAIL_ID, ()):
            rail_total[frame_index] += float(response.normal_force_n)
    body_total = np.sum(np.vstack(list(arrays.values())), axis=0)
    identity = float(np.max(np.abs(body_total - rail_total))) if frames else float("inf")

    mass_kg = float(
        case.vehicle.carbody.mass_kg
        + 2.0 * case.vehicle.bogie.mass_kg
        + 4.0 * case.vehicle.wheelset.mass_kg
    )
    axle_share_n = mass_kg * 9.81 / 4.0
    summary = dict(result.summary or {})
    gates = {name: bool(value) for name, value in (summary.get("gates") or {}).items()}

    report: dict[str, object] = {
        "run": {
            "setup": str(Path(args.setup).resolve().relative_to(ROOT)),
            "speed_kmh": float(resolved.setup.speed_kmh),
            "duration_s": float(resolved.setup.duration_s),
            "output_step_s": float(resolved.setup.output_step_s),
            "x_start_m": x_start,
            "frames": frames,
            "wall_s": round(elapsed, 1),
            "front_axle_from_m": float(stations[0]),
            "front_axle_to_m": float(stations[-1]),
        },
        "gates": gates,
        "result_status": summary.get("result_status"),
        "axle_share_n": axle_share_n,
        "identity_max_abs_n": identity,
        "bodies": {
            name: {"min_kn": float(values.min() / 1e3), "max_kn": float(values.max() / 1e3)}
            for name, values in arrays.items()
        },
    }

    marker: dict[str, float | None] = {}
    for name, values in arrays.items():
        index = first_sustained(values / 1e3, FIRST_LOAD_KN)
        marker[name] = None if index is None else float(stations[index])
    report["first_sustained_load_m"] = marker

    if "frog" in arrays:
        frog_kn = arrays["frog"] / 1e3
        carried = frog_kn >= RELEASE_SHARE * axle_share_n / 1e3
        if carried.any():
            report["frog_peak_kn"] = float(frog_kn.max())
            report["frog_reaches_5pct_m"] = float(stations[int(np.argmax(carried))])
    if "blade" in arrays:
        blade_kn = arrays["blade"] / 1e3
        carried = blade_kn >= RELEASE_SHARE * axle_share_n / 1e3
        if carried.any():
            report["blade_last_5pct_m"] = float(stations[int(np.max(np.nonzero(carried)))])
            report["blade_peak_kn"] = float(blade_kn.max())

    rows = []
    for station in np.arange(np.floor(stations[0]), np.ceil(stations[-1]) + 1.0, 1.0):
        index = int(np.argmin(np.abs(stations - station)))
        row: dict[str, float] = {
            "station_m": round(float(stations[index]), 3),
            "rail_total_kn": round(float(rail_total[index] / 1e3), 3),
        }
        for name, values in arrays.items():
            row[name] = round(float(values[index] / 1e3), 3)
        rows.append(row)
    report["per_metre"] = rows

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"frames {frames}   front axle {stations[0]:.3f} -> {stations[-1]:.3f} m   wall {elapsed:.1f} s")
    print(f"identity  max |sum over bodies - rail total| = {identity:.3e} N   (axle share {axle_share_n / 1e3:.3f} kN)")
    for name, values in arrays.items():
        where = marker[name]
        print(
            f"  {name:>6s}  peak {values.max() / 1e3:9.3f} kN   first >= {FIRST_LOAD_KN:g} kN sustained: "
            + ("never" if where is None else f"{where:.3f} m")
        )
    if "frog_reaches_5pct_m" in report:
        print(
            f"frog reaches {RELEASE_SHARE:.0%} of the axle load at {report['frog_reaches_5pct_m']:.3f} m "
            f"(peak {report['frog_peak_kn']:.3f} kN)"
        )
    if "blade_last_5pct_m" in report:
        print(f"blade last at or above {RELEASE_SHARE:.0%}: {report['blade_last_5pct_m']:.3f} m "
              f"(peak {report['blade_peak_kn']:.3f} kN)")
    print(f"report -> {REPORT}")
    failed = [name for name, value in gates.items() if not value]
    print(
        f"gates {sum(gates.values())}/{len(gates)}"
        + (f"   failed: {', '.join(failed)}" if failed else "")
        + f"   result_status {report['result_status']}"
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
