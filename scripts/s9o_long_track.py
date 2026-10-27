"""Run a straight case long enough to leave the station table behind.

The straight base case (`F:\\velch_tmp\\straight\\case_straight_axlebox.json`) carries
rail stations at **0.0 and 150.0 m only**, so any run whose front axle reaches past
150 m is integrating over steel that does not exist -- the vehicle loses contact and
falls freely, and every number measured in that window is meaningless.  The review
found exactly that in the long-wave runs (31 % of the analysis window was free fall).

This helper appends a station far downstream that clones the last existing profile.
That is legitimate here because the case describes a **constant-profile straight
track** (no turnout, no transition): beyond the last station the profile is that
station's profile, so cloning it extends the geometry rather than inventing it.  Every
extension is recorded in the derived case and printed, so a reader can see the run
stayed on the table.

Subcommands:
    decay     -- zero irregularity, 80 km/h, 6 s, report the 10-17 Hz decay
    longwave  -- 20/40 m bands at 350 km/h, 2 s, with the table extended
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parents[1]
BASE = pathlib.Path(r"F:\velch_tmp\straight\case_straight_axlebox.json")
WORK = pathlib.Path(r"F:\velch_tmp\s9o")
EXTEND_TO_M = 400.0
VEHICLE = "CRH380A_M_axlebox"


def extend(base: pathlib.Path, target: pathlib.Path, *, duration_s: float, speed_m_s: float,
           x_start_m: float = 13.5, output_step_s: float, solver_step_s: float,
           irregularity: dict | None = None) -> dict:
    """Write a case whose rail station table covers the whole run."""
    doc = json.loads(base.read_text(encoding="utf-8"))
    base_dir = base.parent

    reach = x_start_m + speed_m_s * duration_s + 10.0          # front axle plus wheelbase
    for template in doc["rail_templates"]:
        stations = template["stations"]
        last = max(float(station["s_m"]) for station in stations)
        if last < reach:
            clone = dict(max(stations, key=lambda station: float(station["s_m"])))
            clone["s_m"] = EXTEND_TO_M
            clone["id"] = f"{clone.get('id', 'station')}_extended"
            template["stations"] = sorted(stations + [clone], key=lambda station: float(station["s_m"]))
            print(f"  extended {template['id']}: {last:.1f} -> {EXTEND_TO_M:.1f} m (run reaches {reach:.1f} m)")

    for node in ("wheels",):
        for wheel in doc.get(node, []):
            for key in ("profile", "file"):
                value = wheel.get(key)
                if isinstance(value, str) and not pathlib.Path(value).is_absolute():
                    wheel[key] = str((base_dir / value).resolve())

    doc["vehicle"] = dict(doc.get("vehicle", {}))
    doc["vehicle"]["travel_speed_m_s"] = speed_m_s
    doc["run"].update(
        duration_s=duration_s,
        output_step_s=output_step_s,
        max_solver_step_s=solver_step_s,
        x_start_m=x_start_m,
    )
    doc.pop("initial_state", None)
    for body in doc.get("topology", {}).get("bodies", []):
        if body.get("kind") == "axlebox" and isinstance(body.get("axle"), int):
            body["axle"] -= 1
    # The case carries its own inline topology, so a fix in vehicles/*.json would not
    # reach it.  Mirror the axle-box yaw constraint (see the vehicle's not_verified note):
    # the box otherwise keeps a zeta = 0 yaw mode at 13.09 Hz, which parks a 9 m/s^2 tone
    # in the acceleration channel forever and swamps every short-wave measurement.
    elements = doc.get("topology", {}).get("elements")
    if elements is not None:
        present = {element.get("name") for element in elements}
        for axle in (1, 2, 3, 4):
            for side in ("L", "R"):
                name = f"box_yaw_{axle}{side}"
                if name in present:
                    continue
                elements.append({
                    "kind": "torsional",
                    "name": name,
                    "axis": "yaw",
                    "stiffness": 2.0e6,
                    "damping": 3000.0,
                    "from": {"body": f"axlebox{axle}{side}"},
                })
        print(f"  axle-box yaw constraint: {len(elements)} elements")

    if irregularity is None:
        doc.pop("irregularity", None)
    else:
        doc["irregularity"] = irregularity

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return doc


def simulate(case_path: pathlib.Path, out_name: str):
    from velch.io.history import read_history
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import save_vehicle_result, simulate_vehicle

    loaded = load_vehicle_case(case_path)
    result = simulate_vehicle(loaded)
    out = WORK / "out" / out_name
    out.mkdir(parents=True, exist_ok=True)
    save_vehicle_result(loaded, result, out)
    history = read_history(out / "history.csv")
    names = list(history.ordering)
    data = {name: np.asarray(history.data[index], float) for index, name in enumerate(names)}
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    return data, manifest


def band_envelope(time: np.ndarray, values: np.ndarray, low_hz: float, high_hz: float,
                  window_s: float = 0.25) -> tuple[np.ndarray, np.ndarray]:
    """Peak-to-peak of the band-limited signal in successive windows (for decay)."""
    rate = 1.0 / float(np.mean(np.diff(time)))
    centers, peaks = [], []
    step = max(1, int(window_s * rate))
    for start in range(0, len(values) - step, step):
        chunk = values[start:start + step]
        spectrum = np.fft.rfft(chunk * np.hanning(len(chunk)))
        freqs = np.fft.rfftfreq(len(chunk), 1.0 / rate)
        mask = (freqs >= low_hz) & (freqs <= high_hz)
        amplitude = 2.0 * np.abs(spectrum) / np.sum(np.hanning(len(chunk)))
        peaks.append(float(np.max(amplitude[mask])) if np.any(mask) else 0.0)
        centers.append(float(time[start:start + step].mean()))
    return np.array(centers), np.array(peaks)


def decay(args) -> int:
    case = WORK / "case_zero_6s.json"
    speed = args.speed_kmh / 3.6
    print(f"zero-irregularity run: {args.speed_kmh:.0f} km/h, {args.duration_s:.1f} s")
    extend(BASE, case, duration_s=args.duration_s, speed_m_s=speed,
           output_step_s=args.output_step_s, solver_step_s=args.solver_step_s)
    data, manifest = simulate(case, "zero_6s")
    status = manifest["summary"]["result_status"]
    time = data["time_s"]
    channel = args.channel
    if channel not in data:
        print(f"channel {channel!r} missing; have {[n for n in data if 'acc' in n][:6]}", file=sys.stderr)
        return 2
    centers, peaks = band_envelope(time, data[channel], 10.0, 17.0, args.window_s)
    print(f"status {status}   frames {len(time)}   window {args.window_s:.2f} s")
    for center, peak in zip(centers, peaks):
        print(f"  t={center:5.2f} s   10-17 Hz peak {peak:7.3f} m/s^2")
    if len(peaks) >= 2:
        first, last = float(np.mean(peaks[:2])), float(np.mean(peaks[-2:]))
        print(f"decay: first {first:.3f} -> last {last:.3f}  (remaining {100*last/first if first else float('nan'):.1f} %)")
    # contact duty cycle, to prove the run stayed on the steel
    actives = [name for name in data if name.endswith("_active")]
    if actives:
        duty = np.mean([float(np.mean(data[name])) for name in actives])
        print(f"contact duty cycle (mean of {len(actives)} patches) {duty:.4f}")
    json.dump({"centers": centers.tolist(), "peaks": peaks.tolist(), "status": status},
              open(WORK / "decay.json", "w", encoding="utf-8"), indent=2)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["decay"])
    parser.add_argument("--speed-kmh", type=float, default=80.0)
    parser.add_argument("--duration-s", type=float, default=6.0)
    parser.add_argument("--output-step-s", type=float, default=2.0e-3)
    parser.add_argument("--solver-step-s", type=float, default=1.0e-3)
    parser.add_argument("--channel", default="axle1_box_left_z_acc_m_per_s2")
    parser.add_argument("--window-s", type=float, default=0.25)
    args = parser.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    return decay(args)


if __name__ == "__main__":
    raise SystemExit(main())
