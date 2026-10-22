"""Compare Simpack's own contact point / penetration against the Velch geometry scan.

Both frames are the PRR reference frame (y = 0 at the profile origin, z = 0 at
the rail crown), so Simpack's ``y_rail_m`` can be compared directly with the
``y_prr`` used in the Velch gap scans.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, r"F:\ai道岔状态反演辨识\simpack-mcp-2021x\src")

from simpack_mcp.rwp import extract_rwp_channels  # noqa: E402

MAT = Path(
    r"F:\ai道岔状态反演辨识\simpack-mcp-2021x\results"
    r"\case_a47bc7d9e48f40b08628147bfab5c3f4\model.output\350.mat"
)
BASE = "timeInt/RS_result/SRS_S_R/SRS_S_WS_F/SRS_RWP_R"


def series(group: str, channel: int) -> list[float]:
    payload = extract_rwp_channels(MAT, group=group, channels=[channel], count=2401)
    return payload["channels"][0]["values"]


def main() -> None:
    s = series(f"{BASE}/SRS_RWP_R_Pair", 8)
    y_rail = series(f"{BASE}/SRS_RWP_R_1_Adv", 3)
    pen = series(f"{BASE}/SRS_RWP_R_1_Adv", 25)
    force = series(f"{BASE}/SRS_RWP_R_1", 10)
    area = series(f"{BASE}/SRS_RWP_R_1", 6)
    y_wheel = series(f"{BASE}/SRS_RWP_R_1", 2)

    print("s_m      y_rail_mm  pen_mm   N_kN    A_mm2   y_wheel_mm")
    rows = 0
    for i, s_i in enumerate(s):
        if not (79.2 <= s_i <= 81.4):
            continue
        if rows % 6 and abs(s_i - 79.6) > 0.2 and abs(s_i - 80.0) > 0.2:
            rows += 1
            continue
        print(
            f"{s_i:8.4f} {y_rail[i]*1e3:9.3f} {pen[i]*1e3:8.4f} "
            f"{force[i]/1e3:7.2f} {area[i]*1e6:8.2f} {y_wheel[i]*1e3:10.3f}"
        )
        rows += 1

    window = [i for i, s_i in enumerate(s) if 79.2 <= s_i <= 81.4]
    print(
        f"\nwindow samples {len(window)}"
        f"  y_rail {min(y_rail[i] for i in window)*1e3:.2f}..{max(y_rail[i] for i in window)*1e3:.2f} mm"
        f"  pen {min(pen[i] for i in window)*1e3:.4f}..{max(pen[i] for i in window)*1e3:.4f} mm"
        f"  N {min(force[i] for i in window)/1e3:.2f}..{max(force[i] for i in window)/1e3:.2f} kN"
    )


if __name__ == "__main__":
    main()
