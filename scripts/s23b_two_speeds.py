"""Two steady speeds on the same track: which ridges move with speed, and do the depths agree?

A feature locked to the rail (corrugation pitch, sleeper spacing) keeps its **wavelength**, so its frequency
scales with speed: ``f = v / lambda``.  A vehicle mode keeps its **frequency**.  With one steady speed those
two hypotheses are indistinguishable; with two they are one ratio apart.

The same run also tests the short-wave operator from the simulation side: above the axle-box resonance the
response is ``a = (2 pi f_n)^2 * A`` with ``f_n = 24.86 Hz``, so the recovered depth must be the *same number*
at both speeds if the feature really is rail geometry and the operator is right.

Run:  python -X utf8 scripts/s23b_two_speeds.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import scipy.io as sio

FIFTY = Path(r"F:\ai道岔状态反演辨识\75kmh数据\Run_50kmh_E1toE2.mat")
SEVENTY = Path(r"F:\ai道岔状态反演辨识\75kmh数据\Run_75kmh_E1toE2.mat")
WORK = Path(r"F:\velch_tmp\two_speeds")

RATE_HZ = 4000.0
BLOCK = 4096
SECTION_KM = {
    "S1": (4.243, 4.300), "S2": (4.718, 4.805), "S3": (4.855, 4.927),
    "S4": (5.250, 5.352), "S5": (5.438, 5.577), "S6": (5.729, 5.829),
}
BOX_RESONANCE_HZ = 24.86
SHORT_WAVE_GAIN = (2.0 * np.pi * BOX_RESONANCE_HZ) ** 2  # (m/s^2) per m of rail amplitude
DESIGN_WAVELENGTH_M = 0.0275
PEAK_PROMINENCE_DB = 6.0
NEAR_HZ = 2.5


def steady_slice(speed_kmh: np.ndarray, tolerance_kmh: float = 4.0) -> np.ndarray:
    """Samples at the record's steady speed.

    Two km/h was too strict on the 75 km/h pass: it kept only 43 s of the 145 s, which then did not contain a
    whole block for the first section.  Four km/h still excludes the start-up ramp (which spans 30-70 km/h)
    and keeps the two passes comparable.
    """
    mode = float(np.median(speed_kmh))
    return np.abs(speed_kmh - mode) <= tolerance_kmh


def spectrum(values: np.ndarray, rate_hz: float = RATE_HZ) -> tuple[np.ndarray, np.ndarray]:
    window = np.hanning(values.shape[0])
    scaled = values * window[:, None] if values.ndim == 2 else values * window
    transform = np.fft.rfft(scaled, axis=0)
    density = (np.abs(transform) ** 2) * (2.0 / (rate_hz * np.sum(window ** 2)))
    if density.ndim > 1:
        # The two axle-box channels are averaged, not kept apart: this script asks *where* the ridges are,
        # and a per-channel peak finder would have to reconcile two peak lists for the same section.
        density = density.mean(axis=1)
    return np.fft.rfftfreq(values.shape[0], 1.0 / rate_hz), density


def average_spectrum(vertical: np.ndarray, mask: np.ndarray, columns: list[int]):
    """Average the periodograms of every full block inside the mask."""
    runs = np.flatnonzero(np.diff(np.r_[False, mask, False]))
    blocks = []
    for start, stop in zip(runs[::2], runs[1::2], strict=False):
        if stop - start < BLOCK:
            continue
        count = (stop - start) // BLOCK
        usable = vertical[start:start + count * BLOCK, :][:, columns]
        for index in range(count):
            blocks.append(usable[index * BLOCK:(index + 1) * BLOCK])
    if not blocks:
        return None, None, 0
    frequencies, first = spectrum(blocks[0])
    total = first.copy()
    for block in blocks[1:]:
        total += spectrum(block)[1]
    return frequencies, total / len(blocks), len(blocks)


def find_peaks(frequencies: np.ndarray, density: np.ndarray, *, floor_hz: float = 5.0) -> list[dict]:
    power = 10.0 * np.log10(np.maximum(density, 1e-30))
    median = float(np.median(power[frequencies >= floor_hz]))
    peaks = []
    for index in range(1, len(power) - 1):
        if frequencies[index] < floor_hz:
            continue
        if not (power[index] > power[index - 1] and power[index] >= power[index + 1]):
            continue
        prominence = power[index] - median
        if prominence < PEAK_PROMINENCE_DB:
            continue
        peaks.append({"frequency_hz": float(frequencies[index]), "prominence_db": float(prominence)})
    return sorted(peaks, key=lambda peak: -peak["prominence_db"])


def amplitude_at(values: np.ndarray, rate_hz: float, frequency_hz: float) -> float:
    time = np.arange(values.shape[0]) / rate_hz
    design = np.column_stack([np.cos(2.0 * np.pi * frequency_hz * time),
                              np.sin(2.0 * np.pi * frequency_hz * time)])
    coefficients, *_ = np.linalg.lstsq(design, values, rcond=None)
    return float(np.hypot(coefficients[0], coefficients[1]))


def analyse(path: Path, label: str) -> dict:
    payload = sio.loadmat(str(path))
    vertical = np.asarray(payload["Vi_y"], dtype=float)
    speed = np.asarray(payload["Vi_Speed"], dtype=float).ravel()
    position = np.asarray(payload["Vi_pks"], dtype=float).ravel() * 1000.0
    mask = steady_slice(speed)
    steady_speed = float(np.mean(speed[mask]))
    print(f"{label}: {vertical.shape[0]} samples, steady {steady_speed:.2f} km/h, "
          f"{mask.sum() / RATE_HZ:.1f} s, mileage {position[mask][0]:.0f}..{position[mask][-1]:.0f} m")

    sections: dict[str, dict] = {}
    for name, (start_km, stop_km) in SECTION_KM.items():
        inside = mask & (position >= start_km * 1000.0) & (position <= stop_km * 1000.0)
        if inside.sum() < BLOCK:
            sections[name] = {"skipped": "shorter than one block"}
            continue
        frequencies, density, blocks = average_spectrum(vertical, inside, [0, 1])
        if blocks == 0:
            sections[name] = {"skipped": "no whole block at the steady speed"}
            print(f"  {name}: skipped (no whole block at the steady speed)")
            continue
        peaks = find_peaks(frequencies, density)
        design_frequency = steady_speed / 3.6 / DESIGN_WAVELENGTH_M
        amplitude = amplitude_at(vertical[inside][:, 0], RATE_HZ, design_frequency)
        sections[name] = {
            "blocks": blocks,
            "peaks": peaks[:6],
            "design_frequency_hz": design_frequency,
            "amplitude_m_per_s2": amplitude,
            "depth_um": amplitude / SHORT_WAVE_GAIN * 1e6,
        }
        print(f"  {name}: {blocks} blocks, design f {design_frequency:6.1f} Hz, amp {amplitude:.5f} m/s², "
              f"depth {amplitude / SHORT_WAVE_GAIN * 1e6:5.1f} µm, peaks "
              + ", ".join(f"{peak['frequency_hz']:.1f}" for peak in peaks[:4]))
    return {"record": path.name, "steady_speed_kmh": steady_speed,
            "steady_seconds": float(mask.sum() / RATE_HZ), "sections": sections}


def compare(seventy: dict, fifty: dict) -> list[dict]:
    ratio = fifty["steady_speed_kmh"] / seventy["steady_speed_kmh"]
    rows = []
    for name in SECTION_KM:
        peaks75 = (seventy["sections"].get(name) or {}).get("peaks") or []
        peaks50 = (fifty["sections"].get(name) or {}).get("peaks") or []
        if not peaks75 or not peaks50:
            continue
        for peak in peaks75[:3]:
            order = np.array([other["frequency_hz"] / ratio for other in peaks50])
            stay = np.array([other["frequency_hz"] for other in peaks50])
            order_gap = float(np.min(np.abs(order - peak["frequency_hz"]))) if order.size else np.inf
            stay_gap = float(np.min(np.abs(stay - peak["frequency_hz"]))) if stay.size else np.inf
            rows.append({
                "section": name, "frequency_70kmh_hz": round(peak["frequency_hz"], 2),
                "expect_if_wavelength_locked_hz": round(peak["frequency_hz"] / ratio, 2),
                "wavelength_locked_gap_hz": round(order_gap, 2),
                "vehicle_mode_gap_hz": round(stay_gap, 2),
                "verdict": "wavelength-locked" if order_gap < stay_gap and order_gap <= NEAR_HZ else
                           ("vehicle mode" if stay_gap < order_gap and stay_gap <= NEAR_HZ else "unmatched"),
            })
    return rows


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    seventy = analyse(SEVENTY, "70 km/h record")
    fifty = analyse(FIFTY, "50 km/h record")
    rows = compare(seventy, fifty)
    print("\nspeed separation (ratio 50/70 = "
          f"{fifty['steady_speed_kmh'] / seventy['steady_speed_kmh']:.4f}):")
    print(f"{'section':7s} {'f@70':>8s} {'order-locked':>13s} {'gap':>6s} {'gap(same)':>10s}  verdict")
    for row in rows:
        print(f"{row['section']:7s} {row['frequency_70kmh_hz']:8.1f} "
              f"{row['expect_if_wavelength_locked_hz']:13.1f} {row['wavelength_locked_gap_hz']:6.2f} "
              f"{row['vehicle_mode_gap_hz']:10.2f}  {row['verdict']}")

    locked = sum(1 for row in rows if row["verdict"] == "wavelength-locked")
    vehicles = sum(1 for row in rows if row["verdict"] == "vehicle mode")
    depths70 = [s["depth_um"] for s in seventy["sections"].values() if "depth_um" in s]
    depths50 = [s["depth_um"] for s in fifty["sections"].values() if "depth_um" in s]
    print(f"\nwavelength-locked {locked}, vehicle {vehicles}, unmatched {len(rows) - locked - vehicles}")
    if depths70 and depths50:
        print(f"depth at {DESIGN_WAVELENGTH_M * 1000:.1f} mm: 70 km/h median {np.median(depths70):.1f} µm, "
              f"50 km/h median {np.median(depths50):.1f} µm, ratio "
              f"{np.median(depths50) / np.median(depths70):.2f}")

    payload = {"seventy": seventy, "fifty": fifty, "separation": rows,
               "conclusion": {"wavelength_locked": locked, "vehicle_mode": vehicles,
                              "unmatched": len(rows) - locked - vehicles}}
    target = WORK / "two_speeds.json"
    target.write_text(json.dumps(payload, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"written {target}")
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
