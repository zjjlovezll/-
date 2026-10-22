"""Where the remaining gap to Simpack sits, measured on the same station grid.

Both sides are reduced to the same two physical quantities: the front wheelset
vertical position and the right-rail normal force. Everything else is derived
from those, so the comparison does not depend on either solver's internals.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import h5py
import numpy as np

BASE = Path(__file__).resolve().parent
MAT = BASE.parents[2] / "simpack-mcp-2021x" / "results" / "case_a47bc7d9e48f40b08628147bfab5c3f4" / "model.output" / "350.mat"
RUN = BASE / "out_final_full1p2s" / "history.csv"
GROUP = "timeInt/RS_result/SRS_S_R/SRS_S_WS_F/SRS_RWP_R"


def simpack_series() -> dict[str, np.ndarray]:
    with h5py.File(MAT, "r") as handle:
        base = handle[GROUP]

        def channel(name: str) -> np.ndarray:
            return np.asarray(base[name]["values"]).ravel().astype(float)

        pair = base["SRS_RWP_R_Pair"]
        patch = base["SRS_RWP_R_1"]
        adv = base["SRS_RWP_R_1_Adv"]
        z = np.asarray(handle["timeInt/bodyPosTrans/SS_F__S_WS_F__B_WS/z"]["values"]).ravel()
        return {
            # ch_008 is measured in the bogie frame: it is the wheelset station
            # minus the 17.5 m bogie spacing, so shift it onto the track axis.
            "s": np.asarray(pair["ch_008"]["values"]).ravel().astype(float) + 17.5,
            "force": np.asarray(patch["ch_010"]["values"]).ravel().astype(float),
            "pen": np.asarray(adv["ch_025"]["values"]).ravel().astype(float),
            "z": z.astype(float),
        }


def velch_series() -> dict[str, np.ndarray]:
    with RUN.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    s = np.array([float(r["axle1_x_m"]) for r in rows])
    force = np.array([float(r["axle1_right_normal_n"]) for r in rows])
    pen = np.array([float(r["axle1_right_penetration_m"]) for r in rows])
    z = np.array([float(r["axle1_z_m"]) for r in rows])
    return {"s": s, "force": force, "pen": pen, "z": z}


def report(tag: str, data: dict[str, np.ndarray]) -> None:
    s, force, pen, z = data["s"], data["force"], data["pen"], data["z"]
    print(f"\n== {tag} ==")
    print(f"  samples            {len(s)}   s = {s[0]:.3f} .. {s[-1]:.3f} m")
    print(f"  force  min/max     {force.min() / 1e3:8.2f} / {force.max() / 1e3:8.2f} kN"
          f"   argmax s = {s[int(np.argmax(force))]:.3f} m")
    print(f"  z      span        {np.ptp(z) * 1e3:8.3f} mm   (mean {z.mean():.6f} m)")
    print(f"  pen    min/max     {pen.min() * 1e6:8.1f} / {pen.max() * 1e6:8.1f} um")
    print(f"  zero-force samples {int(np.sum(force <= 0.0))}")
    # Effective contact stiffness where the contact is actually loaded.
    good = (pen > 1e-6) & (force > 1e3)
    c = force[good] / pen[good] ** 1.5
    if c.size:
        print(f"  C = N/d^1.5        median {np.median(c):.4e}   p10 {np.percentile(c, 10):.4e}"
              f"   p90 {np.percentile(c, 90):.4e}")
    # Where the force peak is produced, and how hard the surface is there.
    if good.any():
        i = int(np.argmax(force))
        if pen[i] > 0:
            print(f"  at peak: pen {pen[i] * 1e6:.1f} um  ->  implied C {force[i] / pen[i] ** 1.5:.4e}")


def main() -> None:
    sim = simpack_series()
    ref = velch_series()
    report("Simpack", sim)
    report("Velch (final config)", ref)

    # Same-station comparison around the frog.
    grid = np.linspace(79.0, 84.0, 101)
    f_ref = np.interp(grid, ref["s"], ref["force"] * 1e-3)
    f_sim = np.interp(grid, sim["s"], sim["force"] * 1e-3)
    z_ref = np.interp(grid, ref["s"], (ref["z"] - ref["z"].mean()) * 1e3)
    z_sim = np.interp(grid, sim["s"], (sim["z"] - sim["z"].mean()) * 1e3)

    print("\n== frog window 79-84 m, same station grid ==")
    print(f"  force  ours {f_ref.min():7.2f} .. {f_ref.max():7.2f} kN | simpack {f_sim.min():7.2f} .. {f_sim.max():7.2f} kN")
    print(f"  wheel z ours peak {z_ref.max():+.3f} at s={grid[int(np.argmax(z_ref))]:.2f} |"
          f" simpack peak {z_sim.max():+.3f} at s={grid[int(np.argmax(z_sim))]:.2f} mm")
    print(f"  wheel z ours trough {z_ref.min():+.3f} at s={grid[int(np.argmin(z_ref))]:.2f} |"
          f" simpack trough {z_sim.min():+.3f} at s={grid[int(np.argmin(z_sim))]:.2f} mm")
    print(f"  force correlation {np.corrcoef(f_ref, f_sim)[0, 1]:+.3f}"
          f" | wheel-z correlation {np.corrcoef(z_ref, z_sim)[0, 1]:+.3f}")
    worst = np.argsort(-np.abs(f_ref - f_sim))[:5]
    print("  largest force mismatches:")
    for i in sorted(worst):
        print(f"    s={grid[i]:6.2f}  ours {f_ref[i]:7.2f}  simpack {f_sim[i]:7.2f}  "
              f"delta {f_ref[i] - f_sim[i]:+7.2f} kN   z_ours {z_ref[i]:+.3f} z_sim {z_sim[i]:+.3f} mm")

    out = BASE / "cmp_final_vs_simpack.json"
    out.write_text(json.dumps({
        "simpack": {k: float(v.mean()) for k, v in sim.items()},
        "grid": grid.tolist(),
        "force_ours_kn": f_ref.tolist(),
        "force_simpack_kn": f_sim.tolist(),
        "z_ours_mm": z_ref.tolist(),
        "z_simpack_mm": z_sim.tolist(),
    }, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
