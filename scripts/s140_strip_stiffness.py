"""M8 step 11: a strip-integral stiffness built from the real section and the real wheel.

Round 281 rejected the closed-form point contact because C ~ sqrt(R*) made the blade's 1 mm edge look like a
knife.  This replaces the size law with the thing the solver itself uses: integrate the contact over lateral
strips, with the **combined** wheel-plus-rail gap and the **local** combined curvature, so an edge is soft
only where the combined gap really rises fast.

Per station s, per body i (stock, blade):

    h_i(u) = z_body_i(u) - z_wheel(u)          combined approach height, u = lateral offset
    g_i(u) = max(h_i) - h_i(u)                 closed gap at that lateral position
    R_comb(u) = (1/kappa_body(u) + 1/kappa_wheel(u))^-1   local combined radius
    F_i(delta) = sum_u (4/3) E* sqrt(R_comb(u)) max(0, delta - g_i(u))^1.5 du

and the station solves F_stock(delta) + F_blade(delta) = half load for one common delta (the wheel centre
drop), then share = F_blade / half load.  The strip width and E* are common to both bodies, and the share is
a ratio, so the absolute scale of the integral cancels -- what does not cancel is the shape of g_i(u) and
R_comb(u), which is exactly what round 281 got wrong.

Pre-gate, from round 281: the un-bumped run must reach floor <= 0.02 before any bumped run is judged.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s113_profile_inversion as base  # noqa: E402
import s135_floor_diagnosis as diagnosis  # noqa: E402

REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "strip_stiffness.json"
CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
WHEEL = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "sections" / "LMA_x4.prw"
E_STAR_PA = 1.154e11
HALF_LOAD_N = 60153.0
FLOOR_TARGET = 0.02
FIT_LO_M, FIT_HI_M = 57.5, 63.5
STATION_STEP_M = 0.02
STRIP_M = 1.0e-4
HALF_SPAN_M = 0.025


def _read_two_column(path: pathlib.Path) -> tuple[np.ndarray, np.ndarray]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.replace(",", " ").split()
        if len(parts) >= 2:
            try:
                rows.append((float(parts[0]), float(parts[1])))
            except ValueError:
                continue
    data = np.asarray(rows, dtype=float)
    order = np.argsort(data[:, 0])
    return data[order, 0], data[order, 1]


def _second_derivative(y: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Curvature on the same grid, from a centred second difference."""
    curvature = np.full(y.shape, np.nan)
    if y.size < 3:
        return curvature
    for index in range(1, y.size - 1):
        left, right = y[index - 1], y[index + 1]
        span = right - left
        if span <= 0.0:
            continue
        curvature[index] = (z[index + 1] - 2.0 * z[index] + z[index - 1]) * 2.0 / (span * span) * 2.0
    return curvature


def _strips(sample_z: np.ndarray, sample_y: np.ndarray, wheel_y: np.ndarray, wheel_z: np.ndarray) -> dict:
    """Combined approach height, closed gap and local combined radius on a common lateral grid."""
    grid = np.arange(-HALF_SPAN_M, HALF_SPAN_M + 0.5 * STRIP_M, STRIP_M)
    body_z = np.interp(grid, sample_y, sample_z)
    wheel = np.interp(grid, wheel_y, wheel_z)
    height = body_z - wheel
    curvature_body = _second_derivative(grid, body_z)
    curvature_wheel = _second_derivative(grid, wheel)
    with np.errstate(divide="ignore", invalid="ignore"):
        inverse = curvature_body + curvature_wheel
        radius = np.where(np.isfinite(inverse) & (np.abs(inverse) > 1.0e-3), 1.0 / np.abs(inverse), 10.0)
    return {"gap": float(np.max(height)) - height, "radius": radius}


def _force(strips: dict, delta: float) -> float:
    depth = np.clip(delta - strips["gap"], 0.0, None)
    if not np.any(depth > 0.0):
        return 0.0
    stiffness = (4.0 / 3.0) * E_STAR_PA * np.sqrt(strips["radius"])
    return float(np.sum(stiffness * depth ** 1.5) * STRIP_M)


def _model_share() -> tuple[np.ndarray, np.ndarray]:
    from velch.vehicle import load_vehicle_case
    case = load_vehicle_case(CASE)
    rail = [item for item in case.rails if item.id == "axle1_right"][0]
    bodies = {body.id: body for body in rail.contact_bodies}
    wheel_y, wheel_z = _read_two_column(WHEEL)
    stations = np.arange(FIT_LO_M, FIT_HI_M, STATION_STEP_M)
    share = np.full(stations.shape, np.nan)
    for index, station in enumerate(stations):
        try:
            stock = bodies["stock"].series.sample(float(station), 1.0).profile
            blade = bodies["blade"].series.sample(float(station), 1.0).profile
        except Exception:
            continue
        left = _strips(np.asarray(stock.z_m, dtype=float), np.asarray(stock.y_m, dtype=float),
                       wheel_y, wheel_z)
        right = _strips(np.asarray(blade.z_m, dtype=float), np.asarray(blade.y_m, dtype=float),
                        wheel_y, wheel_z)
        low, high = 0.0, 1.0e-3
        while _force(left, high) + _force(right, high) < HALF_LOAD_N and high < 5.0e-2:
            high *= 2.0
        for _ in range(60):
            middle = 0.5 * (low + high)
            if _force(left, middle) + _force(right, middle) < HALF_LOAD_N:
                low = middle
            else:
                high = middle
        delta = 0.5 * (low + high)
        share[index] = _force(right, delta) / (_force(left, delta) + _force(right, delta))
    return stations, share


def floor_of(route: str, model_share: np.ndarray, stations: np.ndarray) -> dict:
    run_id = base._run_id(route)
    loaded = base._load(run_id)
    observed = base._smooth(base._split(loaded), loaded["station"], base.SMOOTH_M)
    row = np.asarray(loaded["station"], dtype=float)
    usable = (row >= FIT_LO_M) & (row <= FIT_HI_M) & np.isfinite(observed) & (observed > 0.02) & (observed < 0.98)
    predicted = np.interp(row[usable], stations, model_share, left=np.nan, right=np.nan)
    keep = np.isfinite(predicted)
    error = predicted[keep] - observed[usable][keep]
    return {"route": route, "run_id": run_id, "usable": int(keep.sum()),
            "floor": float(np.sqrt(np.mean(error ** 2))), "bias": float(np.mean(error))}


def main() -> int:
    stations, share = _model_share()
    rows = [floor_of(route, share, stations) for route in
            ("straight_one_set", "one_set_twopeak", "one_set_threepeak_obs", "one_set_random")]
    null_row = rows[0]
    pre_gate = null_row["floor"] <= FLOOR_TARGET
    passes = pre_gate and all(row["floor"] <= FLOOR_TARGET for row in rows[1:])
    if passes:
        verdict = "the strip integral reproduces the split on the un-bumped run and on all three profiles"
    elif not pre_gate:
        verdict = ("the strip integral still fails the un-bumped run, so the combined wheel-rail gap does not "
                   "carry the split either: the contact layer has to come from the solver, not from a "
                   "closed-form strip model")
    else:
        verdict = ("the strip integral passes the un-bumped run but misses the bumped ones, so the static "
                   "split is right and the composition is what the model still gets wrong")
    payload = {"e_star_pa": E_STAR_PA, "half_load_n": HALF_LOAD_N, "floor_target": FLOOR_TARGET,
               "strip_m": STRIP_M, "half_span_m": HALF_SPAN_M, "station_step_m": STATION_STEP_M,
               "wheel": WHEEL.name, "rows": rows,
               "pre_gate_pass": bool(pre_gate), "all_pass": bool(passes), "verdict": verdict}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{'run':26s} {'usable':>7s} {'floor':>8s} {'bias':>9s}")
    for row in rows:
        print(f"{row['route']:26s} {row['usable']:7d} {row['floor']:8.4f} {row['bias']:+9.4f}")
    print(f"pre-gate (un-bumped run <= {FLOOR_TARGET}): {'PASS' if pre_gate else 'FAIL'}"
          f"   all runs: {'PASS' if passes else 'FAIL'}")
    print(f"VERDICT: {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
