"""Why is the centre valley five times flatter at 100 km/h?  A 2x2 factorial on archived runs.

Round 301 measured that sliding the fitted centre by +-0.60 m costs 66.8 % of residual rms at 80 km/h
but only 11.5 % at 100 km/h, and rejected sampling density as the cause.  Two candidates remain, and they
make different predictions:

    M-A  amplitude: the Gaussian perturbs the share less when it is 56.6 um instead of 66.2 um, so the
         valley is flatter by construction
    M-B  background: the 100 km/h run has a different share field u0 and 496 usable stations instead of
         369, so the operating point sits nearer saturation and the share stops responding to the
         perturbation

Design: hold each background fixed and swap only the amplitude, giving four rises on the same two archives.

    rise(80 bg, 66.22 um) = 66.8 %   (measured, round 301)
    rise(80 bg, 56.56 um) = ?
    rise(100 bg, 56.56 um) = 11.5 %  (measured, round 301)
    rise(100 bg, 66.22 um) = ?

Pre-registered decision rule (written before the two new scans ran)
    background_effect = rise(80, 66.22) / rise(100, 66.22)     -- amplitude held at the larger value
    amplitude_effect  = rise(80, 66.22) / rise(80, 56.56)      -- background held at the reference
    dominant          = whichever ratio is >= 2.0; if both are < 2.0, "joint"

Nothing is re-simulated; both archives already exist under scratch/runs/.
"""

from __future__ import annotations

import json
import pathlib

import numpy as np

SPEEDS_KMH = (80.0, 100.0)
AMPLITUDES_UM = (66.22, 56.56)
CENTRES_M = {80.0: 58.514, 100.0: 58.919}
RIDGE_HALF_M = 0.60
RIDGE_POINTS = 13
DOMINANCE = 2.0
REPORT = pathlib.Path(__file__).resolve().parent.parent / "reports" / "load_split_inversion_2026-10-31" / "valley_factor.json"


def _fields(speed_kmh: float, stride: int = 1) -> dict:
    """Observed share, baseline share and width at every usable station for one archived speed."""
    import s152_cross_speed as cross

    from s113_profile_inversion import _smooth, _split

    import s123_m7_assembly as assembly
    import s124_joint_inversion as joint

    import s119_width_aware_inversion as law

    state = cross.null_state(speed_kmh)
    run = cross.load(cross.RUNS[speed_kmh][1], speed_kmh, cross.RUNS[speed_kmh][2], stride)
    stations = run["station"]
    observed = _smooth(_split(run), stations, 0.20)
    u0 = np.interp(stations, state["station"], state["u0"], left=np.nan, right=np.nan)
    widths = law._width_at(stations, *law._width_table())
    usable = ((stations >= cross.FIT_LO_M) & (stations <= cross.FIT_HI_M)
              & np.isfinite(observed) & np.isfinite(u0)
              & (observed >= cross.SHARE_LO) & (observed <= 1.0))
    return {
        "grid": stations,
        "observed": observed,
        "u0": u0,
        "widths": widths,
        "usable": usable,
        "sigma_of": joint.share_law(assembly.build_law()),
        "width_m": cross.WIDTH_M,
    }


def rise(fields: dict, amplitude_um: float, centre_m: float) -> dict:
    """Peak residual rise over the centre scan, with the amplitude held at a prescribed value."""
    grid, usable = fields["grid"], fields["usable"]
    sigma_of, width_m = fields["sigma_of"], fields["width_m"]
    observed, u0, widths = fields["observed"], fields["u0"], fields["widths"]

    def rms(shift: float) -> float:
        truth = amplitude_um * np.exp(-0.5 * ((grid[usable] - (centre_m + shift)) / width_m) ** 2)
        residual = sigma_of(u0[usable] + truth, widths[usable]) - observed[usable]
        return float(np.sqrt(np.mean(residual ** 2)))

    profile = {float(shift): rms(float(shift)) for shift in np.linspace(-RIDGE_HALF_M, RIDGE_HALF_M, RIDGE_POINTS)}
    base = rms(0.0)
    peak = max(profile.values())
    return {"amplitude_um": float(amplitude_um), "centre_m": float(centre_m),
            "base_rms_um": base, "peak_rms_um": peak, "rise": peak / base - 1.0}


def measure() -> dict:
    table = {}
    for speed in SPEEDS_KMH:
        fields = _fields(speed)
        for amplitude in AMPLITUDES_UM:
            key = f"{speed:g}@{amplitude:.2f}"
            table[key] = rise(fields, amplitude, CENTRES_M[speed])
            table[key]["speed_kmh"] = speed
            table[key]["usable_stations"] = int(fields["usable"].sum())
            share = fields["u0"][fields["usable"]]
            table[key]["share_mean"] = float(share.mean())
            table[key]["share_p90"] = float(np.quantile(share, 0.90))
            # direct measure of local sensitivity: how much the share law moves for a 1 um change of z
            sigma_of = fields["sigma_of"]
            u0 = fields["u0"][fields["usable"]]
            width = fields["widths"][fields["usable"]]
            slope = (sigma_of(u0 + 1.0, width) - sigma_of(u0, width))
            table[key]["d_sigma_per_um"] = float(np.abs(slope).mean())
            table[key]["d_sigma_per_um_p10"] = float(np.quantile(np.abs(slope), 0.10))
    return table


def verdict(table: dict) -> dict:
    reference = table["80@66.22"]["rise"]
    background_effect = reference / table["100@66.22"]["rise"]
    amplitude_effect = reference / table["80@56.56"]["rise"]
    if background_effect >= DOMINANCE and amplitude_effect < DOMINANCE:
        dominant = "background"
    elif amplitude_effect >= DOMINANCE and background_effect < DOMINANCE:
        dominant = "amplitude"
    elif background_effect >= DOMINANCE and amplitude_effect >= DOMINANCE:
        dominant = "joint"
    else:
        dominant = "neither"
    return {
        "background_effect": float(background_effect),
        "amplitude_effect": float(amplitude_effect),
        "dominance_threshold": DOMINANCE,
        "dominant": dominant,
        "rise_by_key": {key: float(entry["rise"]) for key, entry in table.items()},
    }


def main() -> int:
    table = measure()
    print(f"{'key':>12} {'usable':>7} {'share mean':>11} {'share p90':>10} {'dS/du':>7} {'base um':>8} {'peak um':>8} {'rise %':>8}")
    for key, entry in table.items():
        print(f"{key:>12} {entry['usable_stations']:7d} {entry['share_mean']:11.4f} {entry['share_p90']:10.4f} "
              f"{entry['d_sigma_per_um']:7.4f} {entry['base_rms_um']:8.3f} {entry['peak_rms_um']:8.3f} {entry['rise'] * 100:8.1f}")

    result = verdict(table)
    print()
    print(f"background effect (80 at 66.22 vs 100 at 66.22): {result['background_effect']:.2f}x")
    print(f"amplitude effect  (80 at 66.22 vs 80 at 56.56): {result['amplitude_effect']:.2f}x")
    print(f"dominance threshold {DOMINANCE:.1f}x -> dominant mechanism: {result['dominant'].upper()}")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps({"table": table, "verdict": result, "dominance": DOMINANCE}, indent=2),
                      encoding="utf-8")
    print(f"report -> {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
