"""Joint 3-channel, 2-band operator from the S6b broadband run: does a second sensor help?

Everything here is post-processing of one existing simulation (no new runs):
  F:\velch_tmp\s6b\out\history.csv   +  F:\velch_tmp\s6b\broadband.tre
For each band it fits, per channel,  c ~ A cos(w t) + B sin(w t)  against the band-passed profile at
the first axle, then builds H (channels x bands, complex) and the 2x2 Gram S = H^H H.  The point is
to separate "more sensors" from "better model": the same, unchanged transfer chain, only more rows.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(r"F:\ai道岔状态反演辨识\Velch\src")))
from velch.irregularity import read_tre  # noqa: E402

WORK = Path(r"F:\velch_tmp\s6b")
BANDS = ((0.05, 0.10), (1.0, 4.0))          # 0.05-0.10 m, 1.0-4.0 m
SOUND = 0.01                                 # m/s^2, per band (same assumption as S6b)


def load_history(path: Path):
    raw = np.genfromtxt(path, delimiter=",", names=True)
    return {name: np.asarray(raw[name], dtype=float) for name in raw.dtype.names}


def bandpass(values, times, lo_hz, hi_hz):
    order = np.argsort(times)
    values, times = values[order], times[order]
    dt = float(np.median(np.diff(times)))
    spec = np.fft.rfft(values - values.mean())
    freqs = np.fft.rfftfreq(len(values), dt)
    spec[(freqs < lo_hz) | (freqs > hi_hz)] = 0.0
    return np.fft.irfft(spec, len(values))


def fit_complex(signal, times, freq_hz):
    basis = np.column_stack([np.cos(2 * np.pi * freq_hz * times), np.sin(2 * np.pi * freq_hz * times)])
    coef, *_ = np.linalg.lstsq(basis, signal, rcond=None)
    return complex(coef[0], -coef[1])         # Amplitudes read out as |A + iB|


def main() -> int:
    case = json.loads((WORK / "case_broadband.json").read_text(encoding="utf-8"))
    x_start = float(case["run"]["x_start_m"])
    speed = float(case["vehicle"]["travel_speed_m_s"])
    vehicle = case["vehicle"]
    if "axle_offsets_m" in vehicle:
        axles = list(vehicle["axle_offsets_m"])
    else:                                     # derived from the layout: +/- wheelbase/2 inside +/- bogie spacing
        wheelbase = float(vehicle["wheelbase_m"])
        half_spacing = float(vehicle["bogie_half_spacing_m"])
        axles = [-half_spacing - wheelbase / 2, -half_spacing + wheelbase / 2,
                 half_spacing - wheelbase / 2, half_spacing + wheelbase / 2]

    history = load_history(WORK / "out" / "history.csv")
    times = history["time_s"]
    track = read_tre(WORK / "broadband.tre")

    def profile_at_axle(t_s):
        mileage = x_start + speed * np.asarray(t_s) + axles[0]
        return np.interp(mileage, track.s_m, track.vertical_m)

    seen = profile_at_axle(times)
    picks = {
        "wheelset": "axle0_z_acc_m_per_s2",
        "axlebox": next((n for n in history if "box" in n and n.endswith("_z_acc_m_per_s2")), None),
        "bogie": next((n for n in history if n.startswith("bogie1") and n.endswith("_z_acc_m_per_s2")), None),
    }
    picks = {k: v for k, v in picks.items() if v in history}
    print("channels:", picks)
    if len(picks) < 2:
        print("need at least two acceleration channels")
        return 2

    names = list(picks)
    h_matrix = np.zeros((len(names), len(BANDS)), dtype=complex)
    for row, name in enumerate(names):
        acc = bandpass(history[picks[name]], times, 0.5, 990.0)
        for col, (short, long_) in enumerate(BANDS):
            freq = speed / (0.5 * (short + long_))
            reference = fit_complex(seen, times, freq)   # LS at the band centre from the raw profile
            if abs(reference) < 1e-12:
                print(f"  band {short}-{long_} m: no profile content at {freq:.1f} Hz")
                continue
            h_matrix[row, col] = fit_complex(acc, times, freq) / reference

    print("H (rows=channels, cols=bands), per unit track amplitude:")
    for name, row in zip(names, h_matrix):
        print(f"  {name:9s} " + "  ".join(f"{abs(v):12.1f}" for v in row))

    gram = h_matrix.conj().T @ h_matrix
    noise = SOUND ** 2
    def report(tag, matrix):
        """matrix is (channels x bands); Gram = matrix^H matrix, NEA from its inverse."""
        sv = np.linalg.svd(matrix, compute_uv=False)
        cond = float(sv[0] / sv[-1]) if sv[-1] > 0 else float("inf")
        gram = matrix.conj().T @ matrix
        cov = noise * np.linalg.inv(gram)
        nea = np.sqrt(np.diag(cov).real)
        print(f"{tag:22s} cond {cond:8.3f}  min-sv {sv[-1]:12.3e}  NEA " +
              "  ".join(f"{1e6 * v:8.2f}" for v in nea) + " um")
        return cond, nea

    print()
    for i, name in enumerate(names):
        report(f"single: {name}", h_matrix[i:i + 1, :])
    report("joint: all channels", h_matrix)

    singles = [abs(h_matrix[i, :]) for i in range(len(names))]
    print("\nper-band |H| (single-channel best / joint NEA):")
    for col, (short, long_) in enumerate(BANDS):
        best = max(singles, key=lambda row: row[col])[col]
        print(f"  {short:4.2f}-{long_:4.2f} m   best-single {abs(best):10.1f}   "
              f"gain-of-joint {abs(np.linalg.norm(h_matrix[:, col])):10.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
