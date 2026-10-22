"""Dump the peak/valley structure of a few turnout cross-sections (compact)."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from prep_bodies import envelope, load_section  # noqa: E402

BASE = Path(r"F:\ai道岔状态反演辨识\Velch\validation\crh380a_m")
cat = json.loads(Path(r"F:\ai道岔状态反演辨识\Velch\diagnostics\crh380a_m_track_catalog.json")
                 .read_text(encoding="utf-8"))
right = sorted([r for r in cat["profile_references"] if r.get("side") == "right"],
               key=lambda r: r["index"])
by_s = {round(float(r["station_m"]), 4): r for r in right}


def report(target):
    r = min(right, key=lambda r: abs(float(r["station_m"]) - target))
    y, z = load_section(r["path"])
    grid, env = envelope(y, z)
    # compress the envelope to 1 mm bins (max z)
    step = 0.001
    lo, hi = grid[0], grid[-1]
    n = int(np.ceil((hi - lo) / step)) + 1
    g2 = lo + np.arange(n) * step
    idx = np.clip(np.round((grid - lo) / step).astype(int), 0, n - 1)
    e2 = np.full(n, -np.inf)
    np.maximum.at(e2, idx, env)
    ok = np.isfinite(e2)
    e2[~ok] = np.interp(g2[~ok], g2[ok], e2[ok])

    from scipy.signal import find_peaks

    pk, _ = find_peaks(e2, prominence=0.0008)
    vl, _ = find_peaks(-e2, prominence=0.0008)
    print(f"\n--- s={r['station_m']:7.3f}  y=[{lo*1e3:.1f},{hi*1e3:.1f}]  "
          f"zmax={e2.max()*1e3:+.2f} zmin={e2.min()*1e3:+.2f} ---")
    parts = []
    for p in pk:
        parts.append(f"PK y={g2[p]*1e3:6.1f} z={e2[p]*1e3:+6.2f}")
    print("  " + " | ".join(parts))
    parts = []
    for v in vl:
        parts.append(f"VL y={g2[v]*1e3:6.1f} z={e2[v]*1e3:+6.2f}")
    print("  " + " | ".join(parts))


for s in (0.0, 51.117, 52.6, 53.606, 57.304, 60.963, 69.479, 78.538, 80.278, 80.911, 82.428):
    report(s)
