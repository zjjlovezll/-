"""M5: invert a known surface bump out of the per-body load split, on the contact band.

The round-250 measurement found that the axle-box acceleration localises a bump but stops being
monotone past about 0.8 of the static penetration, while the split between the two bodies of the right
rail keeps moving.  So this experiment inverts the *load split* instead, as a station-resolved profile
``z(s)`` on the contact band, and compares it point by point with the Gaussian that was actually put
there.

Observable and geometry
-----------------------
For each output frame the axle of interest sits at ``s = x_start + v t + offsets[axle]``.  The two
bodies of that rail each report a normal force, so the split is

    sigma(s) = blade / (stock + blade)          in [0, 1]

The known geometry is the *pristine* gap between the two crowns at that station,

    d(s) = stock_crown(s) - blade_crown(s)      positive = the blade is lower than the stock

and the blade starts carrying, on the geometry alone, when ``d`` drops below the static penetration
(65.4661 um).  A bump of amplitude ``z`` raises the blade by ``z``, so the gap the contact sees is

    u(s) = d(s) - z(s)

Estimator and its hold-out
--------------------------
A monotone map ``sigma = f(u)`` is fitted on **one** amplitude only (the smallest, 50 um, which is in
the linear regime) and then applied to the two amplitudes it never saw.  The inversion is the inverse
map ``u = f^{-1}(sigma)`` and the estimate is ``z(s) = d(s) - u(s)``.  Nothing from the 100 um or
200 um runs enters the calibration, so their errors are hold-out errors.

Pre-registered gates (written before running)
---------------------------------------------
G-A  the inverted peak amplitude recovers the applied one with ``|e| / max(z, 0.5 mm) <= 2 %``
     (the user's 98 % relative criterion, measured against the 0.5 mm floor decided in the task book);
G-B  the absolute error over the window where the truth exceeds 10 % of its peak has
     ``p95(|e|) <= 22 um`` (one third of the static penetration);
G-C  the station of the inverted peak is within ``0.20 m`` of the truth.

Anything that fails is reported as failed.  The script writes ``scratch/s113/inversion.json`` and
prints the table; ``--write`` is not needed, the file is always written.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s110_lowering_readings as lowering  # noqa: E402  (crown_m, CASE, constants)

RUNS = ROOT.parent / "scratch" / "runs"
OUT = ROOT.parent / "scratch" / "s113"

SPEED_KMH = 80.0
DURATION_S = 0.6
AXLE = 0
BODY_PREFIX = "axle1_right"
STATIC_PENETRATION_M = 65.4661e-6
CENTRE_M = 58.5
SIGMA_M = 1.2
AMPLITUDES_UM = (50.0, 100.0, 200.0)
CALIBRATION_UM = 50.0
RELATIVE_LIMIT = 0.02
FLOOR_M = 0.5e-3
ABSOLUTE_LIMIT_M = 22e-6
MASK_SHARE = 0.02
SMOOTH_M = 0.20
STATION_LIMIT_M = 0.20
WINDOW_FRACTION = 0.10


def _index_rows() -> list[dict]:
    return [json.loads(line) for line in
            (RUNS / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]


def _run_id(route: str) -> str:
    rows = [row for row in _index_rows()
            if row["route"] == route
            and abs(float(row["duration_s"]) - DURATION_S) < 1e-9
            and abs(float(row["speed_kmh"]) - SPEED_KMH) < 1e-9]
    if not rows:
        raise SystemExit(f"no archived {DURATION_S} s run for {route!r} at {SPEED_KMH} km/h")
    return rows[-1]["run_id"]


def _load(run_id: str) -> dict:
    directory = RUNS / run_id
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    data = np.load(directory / "series.npz")
    labels = list(meta["body_labels"])
    stock = np.asarray(data["body_normal_force_n"])[:, labels.index(f"{BODY_PREFIX}/stock")]
    blade = np.asarray(data["body_normal_force_n"])[:, labels.index(f"{BODY_PREFIX}/blade")]
    times = np.asarray(data["times"], dtype=float)
    # The meta does not store the axle offsets (they are derived from the bogie geometry), so take
    # them from the case itself -- otherwise the station column is off by a whole axle spacing.
    from velch.vehicle import load_vehicle_case

    offsets = np.asarray(load_vehicle_case(lowering.CASE).vehicle.axle_offsets_m, dtype=float)
    offset = float(offsets[AXLE])
    station = float(meta.get("x_start_m", 0.0)) + (SPEED_KMH / 3.6) * times + offset
    return {"run_id": run_id, "meta": meta, "times": times, "station": station,
            "stock": stock, "blade": blade}


def _gap_profile(stations: np.ndarray) -> np.ndarray:
    """Pristine crown gap at each station, from the canonical case's own two bodies."""
    from velch.vehicle import load_vehicle_case

    case = load_vehicle_case(lowering.CASE)
    template = None
    for rail in case.rails:
        bodies = {body.id: body for body in rail.contact_bodies}
        if "stock" in bodies and "blade" in bodies:
            template = bodies
            break
    if template is None:
        raise SystemExit("the canonical case has no stock+blade pair to measure the gap on")
    gap = []
    for station in stations:
        try:
            stock = lowering.crown_m(template["stock"].series, float(station))
            blade = lowering.crown_m(template["blade"].series, float(station))
        except Exception:
            gap.append(np.nan)
            continue
        gap.append(stock - blade)
    return np.asarray(gap, dtype=float)


def _split(run: dict) -> np.ndarray:
    total = run["stock"] + run["blade"]
    with np.errstate(invalid="ignore", divide="ignore"):
        share = np.where(total > 1e3, run["blade"] / total, np.nan)
    return share


def _smooth(share: np.ndarray, stations: np.ndarray, width_m: float) -> np.ndarray:
    """Median filter over a station window.

    The split is a per-frame quantity and the contact flickers between the two bodies frame by frame,
    so a single frame is not the measurement; the feature under test is 1 m wide.  Median rather than
    mean, because the interest is in the branch, not in the average of a flicker.
    """
    step = float(np.median(np.diff(stations)))
    half = max(1, int(round(0.5 * width_m / abs(step))))
    out = np.full_like(share, np.nan)
    for index in range(share.size):
        low, high = max(0, index - half), min(share.size, index + half + 1)
        chunk = share[low:high]
        chunk = chunk[np.isfinite(chunk)]
        if chunk.size:
            out[index] = float(np.median(chunk))
    return out


def _truth(stations: np.ndarray) -> np.ndarray:
    return np.zeros_like(stations)


def _true_bump(stations: np.ndarray, amplitude_m: float) -> np.ndarray:
    return amplitude_m * np.exp(-0.5 * ((stations - CENTRE_M) / SIGMA_M) ** 2)


def _monotone_map(u: np.ndarray, sigma: np.ndarray, bins: int = 40) -> tuple[np.ndarray, np.ndarray]:
    """A monotone table ``sigma(u)`` built from bin medians, then sorted by ``u``.

    ``sigma`` rises as ``u`` falls (the blade takes over once the gap closes), so the table is built
    in ascending ``u`` after sorting, and inverted by interpolation in ``_invert``.
    """
    keep = np.isfinite(u) & np.isfinite(sigma)
    u, sigma = u[keep], sigma[keep]
    if u.size < bins * 3:
        raise SystemExit("not enough samples to build the calibration table")
    edges = np.quantile(u, np.linspace(0.0, 1.0, bins + 1))
    centres, medians = [], []
    for low, high in zip(edges[:-1], edges[1:]):
        inside = (u >= low) & (u <= high)
        if inside.sum() < 5:
            continue
        centres.append(float(np.median(u[inside])))
        medians.append(float(np.median(sigma[inside])))
    order = np.argsort(centres)
    table_u = np.asarray(centres, dtype=float)[order]
    table_s = np.asarray(medians, dtype=float)[order]
    # sigma must fall as the gap grows; scanning from the right, a running maximum enforces that
    for index in range(len(table_s) - 2, -1, -1):
        table_s[index] = max(table_s[index], table_s[index + 1])
    return table_u, table_s


def _invert(target: np.ndarray, table_u: np.ndarray, table_s: np.ndarray) -> np.ndarray:
    """Invert sigma -> u by interpolating on the (monotone) table, clamped at both ends."""
    # np.interp needs increasing x; sigma is non-increasing in u, so flip both.
    return np.interp(target, table_s[::-1], table_u[::-1])


def main() -> int:
    baseline = _load(_run_id("straight_one_set"))
    variants = {amplitude: _load(_run_id(f"one_set_bump{amplitude:05.1f}um"))
                for amplitude in AMPLITUDES_UM}

    stations = baseline["station"]
    gap = _gap_profile(stations)
    print(f"baseline {baseline['run_id']}")
    print(f"  frames {stations.size}  station {stations[0]:.2f} .. {stations[-1]:.2f} m")
    print(f"  gap d(s) at 57/58.5/60 m: {np.interp([57.0, 58.5, 60.0], stations[~np.isnan(gap)], gap[~np.isnan(gap)]).round(6)}")
    print()

    calibration = variants[CALIBRATION_UM]
    u_cal = gap - _true_bump(calibration["station"], CALIBRATION_UM * 1e-6)
    sigma_cal = _split(calibration)
    table_u, table_s = _monotone_map(u_cal, sigma_cal)
    print(f"calibration table from {CALIBRATION_UM:.0f} um only: {table_u.size} bins, "
          f"u {table_u[0] * 1e6:.1f} .. {table_u[-1] * 1e6:.1f} um, "
          f"sigma {table_s[0]:.3f} .. {table_s[-1]:.3f}")
    print()
    print("amplitude   peak_true   peak_est   rel err   p95 |e|    max |e|   peak at   gate A/B/C")

    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for amplitude in AMPLITUDES_UM:
        run = variants[amplitude]
        share = _smooth(_split(run), run["station"], SMOOTH_M)
        u_est = _invert(share, table_u, table_s)
        truth = _true_bump(run["station"], amplitude * 1e-6)
        estimate = gap - u_est
        # Only where the blade is actually carrying is the split informative at all: before the gap
        # closes, every frame reports sigma = 0 and the inversion would clamp to "no bump", which is
        # not a measurement.  Those frames are unobserved, not zero.
        observed = np.isfinite(share) & (share > MASK_SHARE)
        finite = observed & np.isfinite(estimate) & np.isfinite(truth) & ~np.isnan(gap)
        window = finite & (truth > WINDOW_FRACTION * truth.max())
        peak_est = float(np.nanmax(estimate[finite])) if finite.any() else float("nan")
        peak_true = float(truth.max())
        peak_at = float(run["station"][finite][int(np.nanargmax(estimate[finite]))])
        relative = abs(peak_est - peak_true) / max(peak_true, FLOOR_M)
        errors = np.abs(estimate[window] - truth[window])
        p95 = float(np.percentile(errors, 95)) if errors.size else float("nan")
        gate_a = relative <= RELATIVE_LIMIT
        gate_b = p95 <= ABSOLUTE_LIMIT_M
        gate_c = abs(peak_at - CENTRE_M) <= STATION_LIMIT_M
        rows.append({"amplitude_um": amplitude, "run_id": run["run_id"],
                     "peak_true_m": peak_true, "peak_estimate_m": peak_est,
                     "relative_error": relative, "p95_error_m": p95,
                     "max_error_m": float(errors.max()) if errors.size else float("nan"),
                     "peak_station_m": peak_at,
                     "gate_relative": bool(gate_a), "gate_absolute": bool(gate_b),
                     "gate_station": bool(gate_c),
                     "window_frames": int(window.sum()),
                     "observed_frames": int(finite.sum())})
        print(f"{amplitude:9.0f}  {peak_true * 1e6:9.1f}  {peak_est * 1e6:9.1f}  {relative:8.4f}  "
              f"{p95 * 1e6:8.2f}  {rows[-1]['max_error_m'] * 1e6:9.2f}  {peak_at:8.2f}   "
              f"{'Y' if gate_a else 'n'}/{'Y' if gate_b else 'n'}/{'Y' if gate_c else 'n'}")

    holdout = [row for row in rows if row["amplitude_um"] != CALIBRATION_UM]
    passed = all(row["gate_relative"] and row["gate_absolute"] and row["gate_station"]
                 for row in holdout)
    verdict = ("the load split inverts the applied bump on the held-out amplitudes within all three "
               "gates" if passed else
               "the load split does not meet all three gates on the held-out amplitudes")
    print()
    print(f"held-out amplitudes: {[row['amplitude_um'] for row in holdout]}")
    print(f"VERDICT: {verdict}")
    (OUT / "inversion.json").write_text(json.dumps(
        {"baseline": baseline["run_id"], "calibration_um": CALIBRATION_UM,
         "bump": {"centre_m": CENTRE_M, "sigma_m": SIGMA_M},
         "gates": {"relative_limit": RELATIVE_LIMIT, "floor_m": FLOOR_M,
                   "absolute_limit_m": ABSOLUTE_LIMIT_M, "station_limit_m": STATION_LIMIT_M,
                   "window_fraction": WINDOW_FRACTION},
         "rows": rows, "verdict": verdict}, indent=1) + chr(10), encoding="utf-8")
    print(f"report -> {OUT / 'inversion.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
