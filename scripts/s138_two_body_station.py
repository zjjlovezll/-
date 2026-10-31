"""M8 step 9: a per-station two-body Hertz forward with no fitted stiffness.

Rounds 277-280 measured five explanations away and left one: the share at a station is not a function of
that station's scalar gap alone.  The measured law is an empirical curve fitted on single bumps of the
whole blade body, so it cannot know that on a rising surface the contact point moves, the normal direction
tilts and the two bodies share the wheel differently.

This module replaces the curve with a per-station contact model:

    per body i (stock, blade):
        crown z_i(s) and local lateral radius R_i(s) from a parabola fit around the crown
        R*_i = (1/R_wheel + 1/R_i)^-1                      R_wheel = 1.27365 m (measured, round 259)
        C_i  = (4/3) E* sqrt(R*_i)                         E* = 1.154e11 Pa
        F_i  = C_i max(0, p - z_i)^1.5
    per station:
        solve F_stock + F_blade = N (60.15 kN per side) for the common wheel-centre height p
        share = F_blade / N

There is nothing to fit: E*, R*_wheel and the sections are all declared.  So the test is a prediction,
not a calibration -- the same three archived runs give the floors directly.

    read   floor = rms(model share - measured share) on two-peak, three-peak and six-component runs
    gate   floor <= 0.02 on all three, including the six-component one the law fails (0.1314)
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

REPORT = ROOT / "reports" / "load_split_inversion_2026-10-31" / "two_body_station.json"
CASE = ROOT / "vehicles" / "turnouts" / "CN60-1100-1_18" / "cases" / "straight_one_set.json"
RUNS_DIR = ROOT.parent / "scratch" / "runs"
E_STAR_PA = 1.154e11
WHEEL_LATERAL_RADIUS_M = 1.27365
HALF_LOAD_N = 60153.0
FLOOR_TARGET = 0.02
FIT_LO_M, FIT_HI_M = 57.5, 63.5
CROWN_WINDOW_M = 3.0e-3


def _curvature_radius(profile, half_window: float = CROWN_WINDOW_M) -> float:
    """Lateral radius of the surface at its crown, from a parabola through points near the top."""
    y = np.asarray(profile.y_m, dtype=float)
    z = np.asarray(profile.z_m, dtype=float)
    order = np.argsort(y)
    y, z = y[order], z[order]
    crown = int(np.argmax(z))
    near = np.abs(y - y[crown]) <= half_window
    if int(near.sum()) < 6:
        return float("inf")
    coefficients = np.polyfit(y[near] - y[crown], z[near] - z[crown], 2)
    # A crown opens *downwards* in z(y): z = z0 - |a| (y - y_c)^2, so the radius is 1 / |2a|.
    # (Taking 2a with its sign returned "inf" for all 300 stations, i.e. a flat model -- round 281.)
    curvature = abs(2.0 * coefficients[0])
    if curvature <= 1.0e-6:
        return float("inf")
    return float(1.0 / curvature)


def _station_arrays() -> dict:
    from velch.vehicle import load_vehicle_case
    case = load_vehicle_case(CASE)
    rail = [item for item in case.rails if item.id == "axle1_right"][0]
    bodies = {body.id: body for body in rail.contact_bodies}
    stock, blade = bodies["stock"], bodies["blade"]
    stations = np.arange(FIT_LO_M, FIT_HI_M, 0.02)
    crowns = {"stock": [], "blade": [], "R": {"stock": [], "blade": []}}
    for station in stations:
        for name, body in (("stock", stock), ("blade", blade)):
            try:
                sample = body.series.sample(float(station), 1.0)
            except Exception:  # outside the body's station range
                crowns[name].append(np.nan)
                crowns["R"][name].append(np.nan)
                continue
            crowns[name].append(float(np.max(np.asarray(sample.profile.z_m, dtype=float))))
            crowns["R"][name].append(_curvature_radius(sample.profile))
    return {"stations": stations, "z_stock": np.asarray(crowns["stock"], dtype=float),
            "z_blade": np.asarray(crowns["blade"], dtype=float),
            "R_stock": np.asarray(crowns["R"]["stock"], dtype=float),
            "R_blade": np.asarray(crowns["R"]["blade"], dtype=float)}


def _stiffness(R_rail: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        inverse = 1.0 / WHEEL_LATERAL_RADIUS_M + 1.0 / R_rail
        R_star = np.where(np.isfinite(inverse) & (inverse > 0.0), 1.0 / inverse, np.inf)
    return 4.0 / 3.0 * E_STAR_PA * np.sqrt(R_star)


def _model_share(arrays: dict) -> np.ndarray:
    """Solve the common wheel-centre height per station and return the blade's share."""
    z_stock, z_blade = arrays["z_stock"], arrays["z_blade"]
    c_stock, c_blade = _stiffness(arrays["R_stock"]), _stiffness(arrays["R_blade"])
    share = np.full(z_stock.shape, np.nan)
    for index in range(z_stock.size):
        if not (np.isfinite(z_stock[index]) and np.isfinite(z_blade[index])):
            continue
        if not (np.isfinite(c_stock[index]) and np.isfinite(c_blade[index])):
            continue
        floor = min(z_stock[index], z_blade[index])

        def total(p: float) -> float:
            return (c_stock[index] * max(0.0, p - z_stock[index]) ** 1.5
                    + c_blade[index] * max(0.0, p - z_blade[index]) ** 1.5)

        low, high = floor, floor + 5.0e-3
        while total(high) < HALF_LOAD_N and high - floor < 50.0e-3:
            high += 5.0e-3
        for _ in range(80):
            middle = 0.5 * (low + high)
            if total(middle) < HALF_LOAD_N:
                low = middle
            else:
                high = middle
        p = 0.5 * (low + high)
        blade_force = c_blade[index] * max(0.0, p - z_blade[index]) ** 1.5
        share[index] = blade_force / HALF_LOAD_N
    return share


def floor_of(route: str, model_share: np.ndarray, stations: np.ndarray) -> dict:
    run_id = base._run_id(route)
    loaded = base._load(run_id)
    observed = base._smooth(base._split(loaded), loaded["station"], base.SMOOTH_M)
    row = loaded["station"]
    usable = (row >= FIT_LO_M) & (row <= FIT_HI_M) & np.isfinite(observed) & (observed > 0.02) & (observed < 0.98)
    predicted = np.interp(row[usable], stations, model_share, left=np.nan, right=np.nan)
    keep = np.isfinite(predicted)
    error = predicted[keep] - observed[usable][keep]
    return {"route": route, "run_id": run_id, "usable": int(keep.sum()),
            "floor": float(np.sqrt(np.mean(error ** 2))), "bias": float(np.mean(error))}


def main() -> int:
    arrays = _station_arrays()
    model = _model_share(arrays)
    finite = np.isfinite(model)
    rows = [floor_of(route, model, arrays["stations"]) for route in
            ("straight_one_set", "one_set_twopeak", "one_set_threepeak_obs", "one_set_random")]
    passes = all(row["floor"] <= FLOOR_TARGET for row in rows[1:])
    payload = {"e_star_pa": E_STAR_PA, "wheel_lateral_radius_m": WHEEL_LATERAL_RADIUS_M,
               "half_load_n": HALF_LOAD_N, "floor_target": FLOOR_TARGET,
               "station_range_m": [FIT_LO_M, FIT_HI_M], "stations_finite": int(finite.sum()),
               "stations_total": int(model.size),
               "R_stock_mm_range": [float(np.nanmin(arrays["R_stock"])) * 1e3,
                                    float(np.nanmax(arrays["R_stock"])) * 1e3],
               "R_blade_mm_range": [float(np.nanmin(arrays["R_blade"])) * 1e3,
                                    float(np.nanmax(arrays["R_blade"])) * 1e3],
               "rows": rows, "all_bumped_runs_pass": bool(passes),
               "verdict": ("a per-station two-body Hertz model with no fitted stiffness reproduces the "
                           "measured split on all three profiles"
                           if passes else
                           "a per-station two-body Hertz model with no fitted stiffness still misses the "
                           "floor, so the residual is not the two-body split either")}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"stations {int(finite.sum())}/{model.size} finite;"
          f" R_stock {payload['R_stock_mm_range'][0]:.0f}..{payload['R_stock_mm_range'][1]:.0f} mm"
          f"  R_blade {payload['R_blade_mm_range'][0]:.0f}..{payload['R_blade_mm_range'][1]:.0f} mm")
    print(f"{'run':26s} {'usable':>7s} {'floor':>8s} {'bias':>9s}")
    for row in rows:
        print(f"{row['route']:26s} {row['usable']:7d} {row['floor']:8.4f} {row['bias']:+9.4f}")
    print(f"all bumped runs under {FLOOR_TARGET}: {'YES' if passes else 'NO'}")
    print(f"VERDICT: {payload['verdict']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
