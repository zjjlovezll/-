"""Does the +A/-A differential cancel the vehicle's own transient, or not?

Reviewer defect D4 said the differential of two independent simulations cancels
only 12-600x, because the 13 Hz limit cycle differed in phase by ~8 deg between
the two runs.  That limit cycle was removed by B027 (the axle-box roll restraint),
so D4 must be re-measured rather than assumed either way.

The test needs no new simulation: every +/- pair on disk already contains the
answer.  If the transient is cancelled, the differential's band rms is flat in
time; if not, the early windows carry an excess that decays.  This script
integrates the differential in 0.25 s windows over the whole record for every
pair in a work directory and prints the ratio of the first window to the last.

Run:  python -X utf8 scripts/s9v_cancellation.py [work_dir]
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from velch.io.history import read_history  # noqa: E402

CHANNEL = "axle1_box_left_z_acc_m_per_s2"
WINDOW_S = 0.25


def series(folder: pathlib.Path, name: str) -> tuple[np.ndarray, np.ndarray]:
    history = read_history(folder / "history.csv")
    time = np.asarray(history.data[history.ordering.index("time_s")], dtype=float)
    if name not in history.ordering:
        name = "axle1_z_acc_m_per_s2"
    values = np.asarray(history.data[history.ordering.index(name)], dtype=float)
    return time, values


def band_rms(values: np.ndarray, rate_hz: float, window: float) -> float:
    count = len(values)
    spectrum = np.fft.rfft(values * np.hanning(count))
    gain = 2.0 / np.sum(np.hanning(count))
    freqs = np.fft.rfftfreq(count, 1.0 / rate_hz)
    mask = (freqs >= 1.0 / window) & (freqs <= 1.0 / (window / 4.0))
    return float(np.sqrt(np.sum(np.abs(spectrum[mask] * gain) ** 2) / 2.0))


def main(argv: list[str]) -> int:
    work = pathlib.Path(argv[1]) if len(argv) > 1 else pathlib.Path(r"F:\velch_tmp\s9s")
    pairs = sorted({item.name[:-5] for item in work.glob("out_*_plus")})
    if not pairs:
        raise SystemExit(f"no +- pairs under {work}")
    print(f"{'pair':>10} {'frames':>7} {'dt ms':>6} {'first':>9} {'last':>9} {'ratio':>7} {'flat':>6}")
    rows = []
    for label in pairs:
        plus = work / f"{label}_plus"
        minus = work / f"{label}_minus"
        if not minus.is_dir():
            continue
        name = CHANNEL
        time, first = series(plus, name)
        _, second = series(minus, name)
        if len(first) != len(second):
            print(f"{label:>10} length mismatch {len(first)} vs {len(second)}")
            continue
        rate = 1.0 / float(time[1] - time[0])
        differential = 0.5 * (first - second)
        edges = np.arange(0.0, time[-1], WINDOW_S)
        levels = []
        for start in edges:
            mask = (time >= start) & (time < start + WINDOW_S)
            if np.count_nonzero(mask) < 8:
                continue
            levels.append(band_rms(differential[mask], rate, WINDOW_S))
        head = float(np.mean(levels[:2]))
        tail = float(np.mean(levels[-2:]))
        # A ratio is only meaningful when the tail is above the arithmetic floor:
        # the small bands settle to ~1e-5 (m/s^2), where any ratio is noise on noise.
        if tail < 1.0e-3:
            flat = "n/a"
            ratio = head / tail if tail > 0 else float("inf")
        else:
            ratio = head / tail if tail > 0 else float("inf")
            flat = "yes" if ratio < 1.25 else "no"
        print(f"{label:>10} {len(first):7d} {1000.0 / rate:6.2f} {head:9.4f} {tail:9.4f} {ratio:7.3f} {flat:>6}")
        rows.append({"pair": label, "first": head, "last": tail, "ratio": ratio, "flat": flat})
    if rows:
        worst = max(rows, key=lambda row: row["ratio"])
        print(f"\nworst first/last ratio {worst['ratio']:.3f} ({worst['pair']})")
        print("reading: ratio ~ 1 means the vehicle's own transient cancels in the +- difference;")
        print("         ratio >> 1 means the early record is dominated by an uncancelled start-up.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
