"""How dense must a PRR station table be to carry a real corrugation?

A corrugation lives on the rail, so the honest representation is the station
table: mileage -> section file.  But the solver interpolates **linearly** between
stations, which multiplies the fundamental of a sinusoid by ``|sinc(pi h / l)|^2``.
This script measures that factor instead of trusting the formula, and prints the
spacing each wavelength needs, together with the number of files it costs.

No solver run is involved: it samples the defect, interpolates, and fits.

Run:  python -X utf8 scripts/s9af_corrugation_density.py
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from velch.corrugation import (
    Corrugation,
    alias_free_step_m,
    interpolation_gain,
    required_step_m,
)

WAVELENGTHS_M = (0.025, 0.050, 0.100, 0.200)
SPACING_FRACTIONS = (1 / 4, 1 / 6, 1 / 8, 1 / 10, 1 / 12, 1 / 16, 1 / 20)
PATCH_M = 2.0
FINE_STEP_M = 1.0e-5


def recovered_amplitude(wavelength_m: float, step_m: float) -> float:
    """Fundamental amplitude after sampling at ``step_m`` and interpolating."""
    count = int(round(PATCH_M / wavelength_m * (wavelength_m / step_m)))
    stations = np.arange(count + 1, dtype=float) * step_m
    lifts = np.sin(2.0 * math.pi * stations / wavelength_m)
    fine = np.arange(0.0, stations[-1], FINE_STEP_M)
    interpolated = np.interp(fine, stations, lifts)
    theta = 2.0 * math.pi * fine / wavelength_m
    basis = np.column_stack((np.cos(theta), np.sin(theta), np.ones_like(theta)))
    coefficients, *_ = np.linalg.lstsq(basis, interpolated, rcond=None)
    return float(math.hypot(coefficients[0], coefficients[1]))


def main() -> int:
    print(f"interpolation of a sinusoid, patch {PATCH_M:g} m, fit on a {FINE_STEP_M*1e6:g} um grid")
    print(f"{'lambda mm':>9} {'h/lambda':>9} {'h mm':>8} {'measured':>9} "
          f"{'|sinc|^2':>9} {'error':>8} {'files/2m':>9}")
    for wavelength in WAVELENGTHS_M:
        for fraction in SPACING_FRACTIONS:
            step = wavelength * fraction
            measured = recovered_amplitude(wavelength, step)
            analytic = interpolation_gain(step, wavelength)
            files = int(math.ceil(PATCH_M / step)) + 1
            print(f"{wavelength*1e3:9.1f} {fraction:9.3f} {step*1e3:8.2f} "
                  f"{measured:9.5f} {analytic:9.5f} {measured-analytic:+8.1e} {files:9d}")
        print()

    print("spacing that keeps the interpolation loss within a tolerance")
    print(f"{'lambda mm':>9} {'1 %':>10} {'3 %':>10} {'5 %':>10} {'Nyquist':>10} "
          f"{'files/2m at 3 %':>16}")
    for wavelength in WAVELENGTHS_M:
        row = [required_step_m(wavelength, tolerance=tolerance) for tolerance in (0.01, 0.03, 0.05)]
        nyquist = alias_free_step_m(wavelength)
        files = int(math.ceil(PATCH_M / row[1])) + 1
        print(f"{wavelength*1e3:9.1f} " + " ".join(f"{value*1e3:10.2f}" for value in row)
              + f" {nyquist*1e3:10.2f} {files:16d}")

    print()
    print("check: a corrugation object and its .tre form agree with the analytic lift")
    defect = Corrugation(period_m=0.050, depth_m=30.0e-6, harmonics=(1.0, 0.3))
    track = defect.track(start_m=10.0, periods=4, step_m=0.0025)
    worst = max(abs(float(track.vertical_m[index]) - defect.at(float(track.s_m[index])))
                for index in range(0, len(track.s_m), 7))
    print(f"  peak-to-peak {defect.depth_m*2*sum(defect.harmonics)*1e6:8.2f} um, "
          f"worst |tre - analytic| {worst:.3e} m over {len(track.s_m)} samples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
