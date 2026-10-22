"""Sweep the Hunt-Crossley damping coefficient on the frog window.

Mechanism under test: after the frog the wheel loses support for ~0.45 mm and
lands again.  With ``normal_damping_n_s_m_1p5 = 1e6`` the effective viscous
coefficient at a 0.4 mm penetration is ``1e6 * sqrt(4e-4) = 2e4 N s/m``, while
critical damping for the 1780 kg wheelset on the ~5.5e5 rad/s contact mode is
about ``2 * 1780 * 553 = 2.0e6 N s/m``.  So the current model bounces almost
elastically (zeta ~ 0.01) and never settles -- the observed 88 Hz limit cycle.

This script clones the wing-body window case with several damping coefficients
(and one restitution-matched ~3e7) and prints peak / lost samples / max
penetration for each.

Usage: python sweep_damping.py [case.json] [axle]
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
sys.path.insert(0, str(ROOT / "src"))

DAMPINGS = (1.0e6, 1.0e7, 3.0e7, 1.0e8)


def main(argv: list[str]) -> int:
    source = Path(argv[1]) if len(argv) > 1 else BASE / "case_frog_I_wing_0p05s.json"
    axle = int(argv[2]) if len(argv) > 2 else 1
    base = json.loads(source.read_text(encoding="utf-8"))
    stem = source.stem
    made = []
    for damping in DAMPINGS:
        case = json.loads(json.dumps(base))
        tag = f"damp{damping:.0e}".replace("+", "")
        case["case_id"] = f"{base['case_id']}_{tag}"
        case["contact"]["normal_damping_n_s_m_1p5"] = damping
        path = BASE / f"{stem}_{tag}.json"
        path.write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")
        made.append((tag, damping, path))

    print(f"source {source.name}  axle {axle}  {len(made)} variants")
    print(f"  {'variant':>10s} {'peak_kN':>9s} {'lost':>7s} {'active':>7s} {'max_pen_mm':>11s} {'dE_J':>9s}")
    for tag, damping, path in made:
        out = BASE / f"out_sweep_{tag}"
        cmd = [sys.executable, "-X", "utf8", "-m", "velch", "run-vehicle", str(path),
               "--output", str(out)]
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
        manifest = out / "manifest.json"
        if not manifest.exists():
            print(f"  {tag:>10s}   FAILED  {proc.stderr.strip().splitlines()[-1:]}")
            continue
        data = json.loads(manifest.read_text(encoding="utf-8"))
        summary = data.get("summary", {})
        peaks = summary.get("peak_normal_force_n") or {}
        active = summary.get("active_output_samples") or {}
        key = f"axle{axle}_right"
        peak = peaks.get(key)
        act = active.get(key)
        # The manifest records no output-sample total; the left rail stays in
        # contact for every sample in this window, so use it as the denominator.
        count = active.get(f"axle{axle}_left") or max(active.values() or [0])
        lost = (count - act) if (act is not None and count) else None
        print(f"  {tag:>10s} {peak / 1e3:9.1f} {lost!s:>7s} {act!s:>7s} "
              f"{summary.get('max_penetration_m', 0) * 1e3:11.4f} "
              f"{summary.get('energy_change_j', 0):9.0f}")
        print(f"             status {summary.get('result_status')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
