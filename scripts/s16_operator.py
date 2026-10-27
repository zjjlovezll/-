"""L3: the same-speed band operator the acceptance layer refused to borrow from 80 km/h.

The 70.8 km/h record cannot be judged with an operator measured at 80 km/h, so this script measures its
own: one synthetic run at the recorded mean speed with a 27.5 mm, 30 um corrugation, from which the
gain (m/s^2 of axle-box acceleration per metre of depth) is read at the corrugation frequency.  The same
frequency is then measured on the real record so the two are compared like with like.

What this operator can and cannot do is fixed by its dimension: one band gives one equation, so it
converts a band amplitude into a **depth estimate**, not into a profile.  The superposition test that
would justify a multi-band inversion needs several bands, and with one recorded speed they would all be
looked at with the same unknown depth.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np

WAVELENGTH_M = 0.0275      # measured median on the record
DEPTH_M = 30.0e-6          # probe depth, the same convention as the short-wave tests
SPEED_KMH = 70.8           # the record's mean, so no extrapolation is asked of the operator
BAND_HZ = 60.0             # +/- around the corrugation frequency for the record's band energy


def project(time_s: np.ndarray, signal: np.ndarray, frequency_hz: float) -> float:
    """Amplitude of the coherent component at one frequency (least squares, no window)."""

    omega = 2.0 * np.pi * frequency_hz
    basis = np.column_stack([np.cos(omega * time_s), np.sin(omega * time_s)])
    coefficients, *_ = np.linalg.lstsq(basis, signal, rcond=None)
    return float(np.hypot(coefficients[0], coefficients[1]))


def model_gain(work: Path, *, duration_s: float, speed_kmh: float | None = None,
               patch_start_m: float | None = None, periods: float | None = None,
               crossing_window: bool = False) -> dict:
    """Gain of the axle-box channel for a corrugation at ``WAVELENGTH_M`` and ``DEPTH_M``.

    The three overrides exist so a speed table can be built: with the defaults this is exactly the
    single-point measurement the record calibration used, and with them the same physics is asked at other
    speeds and other patch lengths without duplicating the routine.
    """
    from velch.vehicle import load_vehicle_case
    from velch.vehicle_solver import simulate_vehicle
    from velch.corrugation import Corrugation
    from velch.irregularity import write_tre

    speed_value = float(SPEED_KMH if speed_kmh is None else speed_kmh)
    speed = speed_value / 3.6
    frequency = speed / WAVELENGTH_M
    start_m = 30.0 if patch_start_m is None else float(patch_start_m)
    period_count = 790.0 if periods is None else float(periods)
    work.mkdir(parents=True, exist_ok=True)
    # The .tre s-axis is absolute mileage, and the case starts at 30 m, so the patch has to cover
    # every axle footprint.  A 0 m patch is silently unreachable -- the loader warns about exactly
    # that ("no axle passes over it"), which is how this was caught.
    track = Corrugation(WAVELENGTH_M, DEPTH_M).track(start_m=start_m, periods=period_count,
                                                    step_m=WAVELENGTH_M / 20.0)
    tre = work / "corrugation.tre"
    write_tre(tre, track)

    base = Path(r"F:\velch_tmp\straight\case_straight_axlebox.json")
    raw = json.loads(base.read_text(encoding="utf-8"))
    raw.pop("initial_state", None)
    raw["vehicle"]["travel_speed_m_s"] = speed
    raw["run"].update({
        # The run start and the patch start are different things: the rail table begins at 30 m and
        # the patch has to sit where a wheel will actually reach it.  Tying them together made every
        # wheel start up to 10 m *past* the patch, which read as a gain 180x too small.
        "x_start_m": 30.0, "duration_s": duration_s, "output_step_s": 1.0 / 8000.0,
        "max_solver_step_s": 1.0 / 16000.0, "curve_radius_m": None,
    })
    raw["irregularity"] = {
        "tre": str(tre), "channels": ["vertical"], "scale": 1.0,
        "start_m": start_m, "end_m": float(track.s_m[-1]), "fade_m": 0.0,
    }
    for body in raw.get("topology", {}).get("bodies", []):
        if body.get("kind") == "axlebox":
            body["axle"] = int(body["axle"]) - 1
    case_path = work / "case_operator.json"
    case_path.write_text(json.dumps(raw, indent=1, ensure_ascii=False), encoding="utf-8")

    case = load_vehicle_case(case_path)
    result = simulate_vehicle(case)
    names = list(result.acceleration_names) if result.acceleration_names else []
    if "axle1_box_left_z_acc_m_per_s2" in names:
        column = names.index("axle1_box_left_z_acc_m_per_s2")
    else:
        raise SystemExit(f"no axle-box vertical channel in {names[:6]}...")
    accelerations = np.asarray(result.accelerations)[:, column]
    time_s = np.asarray(result.times_s)
    # Project over the interval the leading axle spends on the patch, not over the whole record.
    # Without this the answer depends on how much dead record surrounds the patch: the same speed
    # read 2.755e4 (790 periods, axle already inside, whole record) and 2.115e4 (240 periods, axle at
    # the edge) -- a 23 % difference that was pure bookkeeping.
    if crossing_window:
        enter = (start_m - 30.0 - 10.0) / speed
        leave = (start_m + period_count * WAVELENGTH_M - 30.0 - 10.0) / speed
        inside = (time_s >= enter) & (time_s <= leave)
        if np.count_nonzero(inside) < 64:
            raise SystemExit(f"crossing window {enter:.3f}-{leave:.3f} s holds "
                             f"{np.count_nonzero(inside)} samples; lengthen duration_s")
        window_time = time_s[inside]
        window_values = accelerations[inside]
    else:
        window_time = time_s
        window_values = accelerations
    amplitude = project(window_time, window_values, frequency)
    return {
        "speed_kmh": speed_value,
        "wavelength_mm": WAVELENGTH_M * 1000.0,
        "frequency_hz": frequency,
        "probe_depth_um": DEPTH_M * 1e6,
        "amplitude_m_per_s2": amplitude,
        "gain_per_m": amplitude / DEPTH_M,
        "status": result.summary.get("result_status"),
        "duration_s": duration_s,
        "design": {
            "periods": period_count,
            "patch_start_m": start_m,
            "patch_length_m": period_count * WAVELENGTH_M,
            "crossing_window": bool(crossing_window),
            "leading_axle_offset_m": 10.0,
        },
    }


def record_amplitude(data_dir: Path, frequency_hz: float) -> dict:
    import s13_admission as gate

    files = sorted(data_dir.glob("*.mat"))
    if not files:
        raise SystemExit(f"no .mat under {data_dir}")
    data = gate.load(files[0])
    time_s = gate._flat(data["Vi_t"])
    channels = data["Vi_y"]
    rate = float(1.0 / np.median(np.diff(time_s)))
    low = max(50.0, frequency_hz - BAND_HZ)
    high = min(0.95 * 0.5 * rate, frequency_hz + BAND_HZ)
    from scipy.signal import butter, filtfilt

    b, a = butter(4, [low / (0.5 * rate), high / (0.5 * rate)], btype="band")
    amplitudes = [project(time_s, filtfilt(b, a, channels[:, column]), frequency_hz)
                  for column in range(channels.shape[1])]
    return {
        "file": files[0].name,
        "rate_hz": rate,
        "band_hz": [low, high],
        "amplitude_m_per_s2": amplitudes,
        "amplitude_median_m_per_s2": float(np.median(amplitudes)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path(r"F:\ai道岔状态反演辨识\75kmh数据"))
    parser.add_argument("--work", type=Path, default=Path(r"F:\velch_tmp\operator70"))
    parser.add_argument("--output", type=Path, default=Path(r"F:\velch_tmp\verdict\operator.json"))
    parser.add_argument("--duration", type=float, default=0.08)
    args = parser.parse_args(argv)

    model = model_gain(args.work, duration_s=args.duration)
    print(f"model: v {model['speed_kmh']:.1f} km/h, lambda {model['wavelength_mm']:.1f} mm -> "
          f"{model['frequency_hz']:.1f} Hz, amplitude {model['amplitude_m_per_s2']:.4f} m/s^2 for "
          f"{model['probe_depth_um']:.0f} um, gain {model['gain_per_m']:.4g} (m/s^2)/m, {model['status']}")

    record = record_amplitude(args.data, model["frequency_hz"])
    print(f"record: {record['file']} band {record['band_hz'][0]:.0f}-{record['band_hz'][1]:.0f} Hz, "
          f"amplitude {record['amplitude_median_m_per_s2']:.4f} m/s^2")

    implied_um = record["amplitude_median_m_per_s2"] / model["gain_per_m"] * 1e6
    verdict = {
        "operator": model,
        "record": record,
        "implied_depth_um": implied_um,
        "single_band": True,
        "note": "one band, one equation: this converts a band amplitude into a depth, not a profile, "
                "and it is valid only at the recorded mean speed",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(verdict, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"implied depth {implied_um:.1f} um (single band, detection level)")
    print(f"verdict: OPERATOR-BUILT -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
