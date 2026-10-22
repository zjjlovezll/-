"""Compare the three B2 runs: coarse output / fine output / tight step."""

from __future__ import annotations

import json
import pathlib

BASE = pathlib.Path(__file__).resolve().parent


def load(tag: str) -> dict:
    manifest = json.loads(
        (BASE / f"out_B2_{tag}" / "manifest.json").read_text(encoding="utf-8")
    )
    summary = manifest["summary"]
    return {
        "tag": tag,
        "nfev": summary["solver"]["nfev"],
        "peak_max": max(summary["peak_normal_force_n"].values()),
        "axle2_right": summary["peak_normal_force_n"]["axle2_right"],
        "max_penetration_m": summary["max_penetration_m"],
        "energy_change_j": summary["energy_change_j"],
        "active": sum(summary["active_output_samples"].values()),
    }


def main() -> int:
    rows = [load(tag) for tag in ("coarse", "fine", "tightstep")]
    reference = rows[0]
    print(f"{'variant':<12}{'nfev':>7}{'peak kN':>10}{'axle2R kN':>11}{'maxpen um':>11}{'d peak %':>10}")
    for row in rows:
        delta = (row["peak_max"] - reference["peak_max"]) / reference["peak_max"] * 100.0
        print(
            f"{row['tag']:<12}{row['nfev']:>7}{row['peak_max'] / 1e3:>10.3f}"
            f"{row['axle2_right'] / 1e3:>11.3f}{row['max_penetration_m'] * 1e6:>11.2f}"
            f"{delta:>10.3f}"
        )
    coarse, fine, tight = rows
    print()
    print(
        "interpretation: if tightstep (coarse output, 4x finer integration) matches fine,"
        " the 2.57 % is integration resolution; if it stays at coarse, it is output sampling."
    )
    print(
        f"  fine  - coarse = {(fine['peak_max'] - coarse['peak_max']) / 1e3:+.3f} kN "
        f"({(fine['peak_max'] - coarse['peak_max']) / coarse['peak_max'] * 100:+.3f} %)"
    )
    print(
        f"  tight - coarse = {(tight['peak_max'] - coarse['peak_max']) / 1e3:+.3f} kN "
        f"({(tight['peak_max'] - coarse['peak_max']) / coarse['peak_max'] * 100:+.3f} %)"
    )
    out = BASE / "probe_event_resolution_three.json"
    out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
