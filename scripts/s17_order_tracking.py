"""Order tracking: resample the record by mileage before any wavelength is believed.

A corrugation is a fixed wavelength on the rail, so its *frequency* moves whenever the speed does.  This
record runs from a few km/h up to 85, which means a fixed-frequency projection at 715 Hz measures a line
that is only there for the instants the vehicle happened to travel at 70.8 km/h.  Resampling the
acceleration against the recorded position turns the line into a fixed **spatial** frequency, where one
number per wavelength is finally meaningful.

Outputs, for the 18-40 mm band the corrugation lives in:

* the spatial peak wavelength, an independent read of the 27.5 mm the window analysis found;
* the coherent amplitude at that wavelength, which divided by the same-speed operator gives a depth.

The depth is still a single-band estimate, so it is a magnitude with no profile in it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

STEP_M = 0.005           # 5 mm sampling in space: 5.5 points per 27.5 mm cycle
BAND_MM = (18.0, 40.0)
OPERATOR_GAIN = 2.755e04  # (m/s^2)/m, measured at 70.8 km/h by s16_operator.py


def spatial_profile(position_m: np.ndarray, signal: np.ndarray, step_m: float) -> tuple[np.ndarray, np.ndarray]:
    """Resample one channel onto a uniform mileage grid.

    ``np.interp`` needs a monotone axis; the record is monotone by L0, but repeated mileage at
    standstill is allowed there, so duplicates are trimmed by keeping the first of each plateau.
    """

    keep = np.concatenate(([True], np.diff(position_m) > 0.0))
    grid_position = position_m[keep]
    grid_signal = signal[keep]
    start = float(np.ceil(grid_position[0] / step_m) * step_m)
    stop = float(np.floor(grid_position[-1] / step_m) * step_m)
    grid = np.arange(start, stop, step_m)
    return grid, np.interp(grid, grid_position, grid_signal)


def spatial_spectrum(grid: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    step = float(np.median(np.diff(grid)))
    window = np.hanning(values.size)
    spectrum = np.abs(np.fft.rfft((values - values.mean()) * window))
    wavelengths = np.divide(1.0, np.fft.rfftfreq(values.size, d=step), out=np.full(values.size // 2 + 1, np.inf),
                            where=np.fft.rfftfreq(values.size, d=step) > 0.0)
    return wavelengths, spectrum


def coherent_at(grid: np.ndarray, values: np.ndarray, wavelength_m: float) -> float:
    wave_number = 2.0 * np.pi / wavelength_m
    basis = np.column_stack([np.cos(wave_number * grid), np.sin(wave_number * grid)])
    coefficients, *_ = np.linalg.lstsq(basis, values, rcond=None)
    return float(np.hypot(coefficients[0], coefficients[1]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path(r"F:\ai道岔状态反演辨识\75kmh数据"))
    parser.add_argument("--output", type=Path, default=Path(r"F:\velch_tmp\verdict\order_tracking.json"))
    parser.add_argument("--gain", type=float, default=OPERATOR_GAIN)
    args = parser.parse_args(argv)

    import s13_admission as gate

    files = sorted(args.data.glob("*.mat"))
    if not files:
        raise SystemExit(f"no .mat under {args.data}")
    data = gate.load(files[0])
    position_m = gate._flat(data["Vi_pks"]) * 1000.0
    channels = np.asarray(data["Vi_y"], dtype=float)

    low_m, high_m = BAND_MM[0] / 1000.0, BAND_MM[1] / 1000.0
    results = []
    for column in range(channels.shape[1]):
        grid, values = spatial_profile(position_m, channels[:, column], STEP_M)
        wavelengths, spectrum = spatial_spectrum(grid, values)
        inside = (wavelengths >= low_m) & (wavelengths <= high_m) & np.isfinite(wavelengths)
        if not np.any(inside):
            continue
        band = np.where(inside)[0]
        peak_index = int(band[int(np.argmax(spectrum[band]))])
        peak_mm = float(wavelengths[peak_index] * 1000.0)
        amplitude = coherent_at(grid, values, float(wavelengths[peak_index]))
        results.append({
            "column": column,
            "samples": int(grid.size),
            "span_m": float(grid[-1] - grid[0]),
            "peak_wavelength_mm": peak_mm,
            "amplitude_m_per_s2": amplitude,
            "implied_depth_um": amplitude / args.gain * 1e6,
        })
        print(f"column {column}: span {grid[-1] - grid[0]:7.1f} m, {grid.size:7d} samples, "
              f"spatial peak {peak_mm:6.2f} mm, amplitude {amplitude:.4f} m/s^2, "
              f"implied depth {amplitude / args.gain * 1e6:7.1f} um")

    if not results:
        raise SystemExit("no channel carried energy inside the 18-40 mm band")

    # Depth section by section.  A whole-record projection averages over the stretches where no
    # corrugation exists, so the duty factor (557 m of section inside 2505 m of track) sits in the number
    # and must come out before any depth is believed.
    section_rows = []
    try:
        import s10_measured_corrugation as detector
        sections = detector.SECTIONS
    except Exception:
        sections = []
    for section in sections:
        # s10 stores (name, start_m, stop_m) with the mileages already in metres.
        name, start_m, stop_m = section[0], float(section[1]), float(section[2])
        for column in range(channels.shape[1]):
            mask = (position_m >= start_m) & (position_m <= stop_m)
            if np.count_nonzero(mask) < 1000:
                continue
            grid, values = spatial_profile(position_m[mask], channels[mask, column], STEP_M)
            amplitude = coherent_at(grid, values, 0.0275)
            section_rows.append({
                "section": name,
                "column": column,
                "amplitude_m_per_s2": amplitude,
                "depth_um": amplitude / args.gain * 1e6,
            })
    if section_rows:
        by_section = {}
        for row in section_rows:
            by_section.setdefault(row["section"], []).append(row["depth_um"])
        print("depth inside each section (um, at 27.5 mm):")
        for name, depths in by_section.items():
            print(f"  {name}: " + ", ".join(f"{depth:6.1f}" for depth in depths))
    if section_rows:
        verdict_sections = [row["depth_um"] for row in section_rows]
    else:
        verdict_sections = []

    depths = [row["implied_depth_um"] for row in results]
    wavelengths = [row["peak_wavelength_mm"] for row in results]
    verdict = {
        "file": files[0].name,
        "step_m": STEP_M,
        "band_mm": list(BAND_MM),
        "gain_per_m": args.gain,
        "columns": results,
        "depth_um_median": float(np.median(depths)),
        "wavelength_mm_median": float(np.median(wavelengths)),
        "in_corrugation_range": all(5.0 <= depth <= 400.0 for depth in depths),
        "section_depths_um": section_rows,
        "section_depth_median_um": float(np.median(verdict_sections)) if verdict_sections else None,
        "section_duty_fraction": (sum(
            float(section[2]) - float(section[1]) for section in sections
        ) / float(position_m[-1] - position_m[0])) if sections else None,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(verdict, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"median wavelength {verdict['wavelength_mm_median']:.2f} mm, "
          f"median depth {verdict['depth_um_median']:.1f} um "
          f"({'inside' if verdict['in_corrugation_range'] else 'outside'} the 5-400 um corrugation band)")
    print(f"verdict: ORDER-TRACKED -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
