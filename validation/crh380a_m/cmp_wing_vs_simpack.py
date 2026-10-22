"""Compare the wing-rail run against Simpack's own contact force series.

Reads our `out_wing_frog_0p05s/history.csv`, extracts the axle-1 right/left normal
forces and the wheelset vertical position, then samples Simpack's `SRS_RWP_R_Pair`
channel 1 (Q, the vertical wheel-rail force of the pair) and channel 8 (s) from the
same 350 km/h 1.2 s run, aligning both on longitudinal position.

Outputs a table for 79.0-84.0 m and a PNG figure.
"""

from __future__ import annotations

import csv
import json
import pathlib
import sys

sys.path.insert(0, r"F:\ai道岔状态反演辨识\simpack-mcp-2021x\src")

from simpack_mcp.rwp import extract_rwp_channels  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
MAT = (
    r"F:\ai道岔状态反演辨识\simpack-mcp-2021x\results"
    r"\case_a47bc7d9e48f40b08628147bfab5c3f4\model.output\350.mat"
)
BASE = "timeInt/RS_result/SRS_S_R/SRS_S_WS_F/SRS_RWP_R"


def simp(channel: int) -> list[float]:
    payload = extract_rwp_channels(MAT, group=f"{BASE}/SRS_RWP_R_Pair", channels=[channel], count=2401)
    return payload["channels"][0]["values"]


def our_history(run: pathlib.Path) -> dict[str, list[float]]:
    with (run / "history.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    out: dict[str, list[float]] = {}
    for key in rows[0]:
        out[key] = [float(r[key]) for r in rows]
    return out


def interp(xs: list[float], ys: list[float], targets: list[float]) -> list[float]:
    out = []
    j = 0
    for t in targets:
        while j + 1 < len(xs) and xs[j + 1] < t:
            j += 1
        if j + 1 >= len(xs):
            out.append(float("nan"))
            continue
        x0, x1 = xs[j], xs[j + 1]
        y0, y1 = ys[j], ys[j + 1]
        out.append(y0 if x1 == x0 else y0 + (y1 - y0) * (t - x0) / (x1 - x0))
    return out


def main() -> None:
    run = HERE / (sys.argv[1] if len(sys.argv) > 1 else "out_wing_frog_0p05s")
    hist = our_history(run)
    cols = sorted(hist)
    print("history columns:", ", ".join(cols))

    x = hist["axle1_x_m"]
    f_right = [v / 1e3 for v in hist["axle1_right_normal_n"]]
    f_left = [v / 1e3 for v in hist["axle1_left_normal_n"]]
    z = hist.get("axle1_z_m", [float("nan")] * len(x))

    s_simp = simp(8)
    q_simp = [v / 1e3 for v in simp(1)]
    q_on_ours = interp(s_simp, q_simp, x)

    pairs = [(xi, a, b) for xi, a, b in zip(x, f_right, q_on_ours) if 79.0 <= xi <= 84.0 and b == b]
    if pairs:
        diffs = [a - b for _, a, b in pairs]
        print(f"\naligned samples 79-84 m: {len(pairs)}")
        print(f"  our peak {max(a for _, a, _ in pairs):8.1f} kN   Simpack peak {max(b for _, _, b in pairs):8.1f} kN")
        print(f"  mean a={sum(a for _,a,_ in pairs)/len(pairs):7.1f}  b={sum(b for _,_,b in pairs)/len(pairs):7.1f}")
        print(f"  diff: max |d| {max(abs(d) for d in diffs):7.1f} kN   mean d {sum(diffs)/len(diffs):+7.1f} kN")

    print("\n   x_m      our_R   simp_R    our_L    z_mm")
    for i, xi in enumerate(x):
        if not (79.0 <= xi <= 84.0):
            continue
        if abs(xi * 20 - round(xi * 20)) > 0.02:
            continue
        print(f"  {xi:7.3f} {f_right[i]:8.1f} {q_on_ours[i]:8.1f} {f_left[i]:8.1f} {z[i]*1e3:7.3f}")

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # pragma: no cover
        print(f"plot skipped: {exc}")
        return

    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    axes[0].plot(x, f_right, lw=1.2, label="Velch (wing body)")
    axes[0].plot(s_simp, q_simp, lw=1.0, alpha=0.75, label="Simpack RWP_R (Q)")
    axes[0].set_ylabel("right normal force (kN)")
    axes[0].axhline(596, color="0.6", ls=":", lw=0.9, label="previous Velch peak 596 kN")
    axes[0].legend(fontsize=8)
    axes[0].grid(alpha=0.3)
    axes[1].plot(x, z, lw=1.2, color="C2")
    axes[1].set_ylabel("wheelset z (m)")
    axes[1].set_xlabel("longitudinal position x (m)")
    axes[1].set_xlim(79.0, 84.0)
    axes[1].grid(alpha=0.3)
    fig.suptitle("CRH380A_M 350 km/h, frog passage: right-rail normal force")
    fig.tight_layout()
    out = HERE / f"{run.name}_vs_simpack.png"
    fig.savefig(out, dpi=150)
    print(f"\nwrote {out}")
    (HERE / f"{run.name}_vs_simpack.json").write_text(
        json.dumps(
            {
                "our_peak_kN": max(f_right),
                "simpack_peak_kN": max(q_simp),
                "window": [79.0, 84.0],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
