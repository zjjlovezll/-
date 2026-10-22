"""Settle the 0.65 mm question with Simpack's own contact coordinates.

Element 80 reports the contact point on BOTH bodies (x/y/z of the wheel point and
of the rail point).  That lets us ask a purely factual question instead of
inferring: at the same station, is Simpack's *rail surface* at the same height as
our PRR surface, or is its *wheel* somewhere else?

Outputs
-------
1. lateral offset  d = y_rail - y_wheel  (settles the 6.5 vs 6.745 mm question)
2. rail surface z vs our PRR surface at the same (s, y)
3. wheel contact height vs our static pose
"""
from __future__ import annotations

import sys

sys.path.insert(0, r"F:\ai道岔状态反演辨识\simpack-mcp-2021x\src")
sys.path.insert(0, r"F:\ai道岔状态反演辨识\Velch\src")

from simpack_mcp.rwp import extract_rwp_channels  # noqa: E402

MAT = (
    r"F:\ai道岔状态反演辨识\simpack-mcp-2021x\results"
    r"\case_a47bc7d9e48f40b08628147bfab5c3f4\model.output\350.mat"
)
BASE = "timeInt/RS_result/SRS_S_R/SRS_S_WS_F/SRS_RWP_R"


def series(group: str, channel: int) -> list[float]:
    payload = extract_rwp_channels(MAT, group=group, channels=[channel], count=2401)
    return payload["channels"][0]["values"]


def main() -> None:
    s = series(f"{BASE}/SRS_RWP_R_Pair", 8)
    patch = {c: series(f"{BASE}/SRS_RWP_R_1", c) for c in (2, 3, 6, 10)}
    adv = {c: series(f"{BASE}/SRS_RWP_R_1_Adv", c) for c in (1, 3, 4, 5, 6, 25)}
    n_patch = series(f"{BASE}/SRS_RWP_R_Pair", 22)

    print("== 1. lateral offset  d = y_rail - y_wheel (mm) ==")
    deltas = [adv[3][i] - patch[2][i] for i in range(len(s))]
    flat = [deltas[i] for i, si in enumerate(s) if 20.0 <= si <= 45.0]
    frog = [deltas[i] for i, si in enumerate(s) if 79.9 <= si <= 80.4]
    print(f"  whole run : min {min(deltas)*1e3:+.4f}  max {max(deltas)*1e3:+.4f}  "
          f"median {sorted(deltas)[len(deltas)//2]*1e3:+.4f}")
    print(f"  flat 20-45: min {min(flat)*1e3:+.4f}  max {max(flat)*1e3:+.4f}  "
          f"median {sorted(flat)[len(flat)//2]*1e3:+.4f}")
    print(f"  frog 79.9-80.4: median {sorted(frog)[len(frog)//2]*1e3:+.4f}")

    print("\n== 2. contact coordinates around the frog ==")
    print("s_m      y_rail  z_rail   y_wheel  z_wheel  pen     N_kN   np")
    for i, si in enumerate(s):
        if not (79.85 <= si <= 80.45):
            continue
        print(
            f"{si:8.4f} {adv[3][i]*1e3:8.3f} {adv[4][i]*1e3:8.4f} "
            f"{patch[2][i]*1e3:8.3f} {adv[1][i]*1e3:8.4f} "
            f"{adv[25][i]*1e3:7.4f} {patch[10][i]/1e3:7.2f} {n_patch[i]:4.0f}"
        )

    print("\n== 3. rail surface z from Simpack vs our profile (same station) ==")
    from velch.profiles import load_profile  # noqa: E402

    stations = [
        (40.0, None),
        (79.9206, r"F:\ai道岔状态反演辨识\Velch\diagnostics\profiles\Profile_Mileage_R79.9206.prr"),
        (80.0044, r"F:\ai道岔状态反演辨识\Velch\diagnostics\profiles\Profile_Mileage_R80.0044.prr"),
    ]
    for target, path in stations:
        if path is None:
            print(f"  s={target}: (skip, no single file)")
            continue
        profile = load_profile(
            path, file_format="prr", surface="rail_top",
            y_sign=1, z_sign=-1, y_offset_m=0.753, z_offset_m=0.0,
        )
        import numpy as np

        idx = min(range(len(s)), key=lambda k: abs(s[k] - target))
        y_r = adv[3][idx]
        z_r = adv[4][idx]
        ours = float(np.interp(y_r, profile.y_m, profile.z_m))
        print(
            f"  s={s[idx]:.4f}  y_rail={y_r*1e3:+.3f} mm  "
            f"Simpack z_rail={z_r*1e3:+.4f} mm  ours={ours*1e3:+.4f} mm  "
            f"diff={(z_r-ours)*1e3:+.4f} mm"
        )


if __name__ == "__main__":
    main()
