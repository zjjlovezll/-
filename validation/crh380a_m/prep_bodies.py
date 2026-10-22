"""Turnout rail-body reconnaissance: segment each PRR cross-section into physically
separate rail bodies, then track them along the longitudinal direction.

Output is a machine-readable catalog (JSON) plus a console report, so the body
labels can be audited against the turnout design before any solver change.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from velch.profiles import load_profile  # noqa: E402

BASE = Path(r"F:\ai道岔状态反演辨识\Velch\validation\crh380a_m")
CATALOG = Path(r"F:\ai道岔状态反演辨识\Velch\diagnostics\crh380a_m_track_catalog.json")

DY = 0.0002          # 0.2 mm lateral grid for the envelope
PROMINENCE = 0.0010  # 1 mm: peaks lower than this are the same physical head
MIN_WIDTH = 0.004    # 4 mm: thinner cells are discretisation crumbs
SMOOTH_NODES = 9     # envelope pre-smoothing (odd, in grid nodes => 1.6 mm)


def envelope(y, z, dy=DY, nodes=SMOOTH_NODES):
    """Max-z envelope on a uniform lateral grid, lightly median-smoothed.

    The median filter removes single-node spikes without moving a genuine edge
    (a median never shifts a step), which is why it is preferred to a mean here.
    """
    lo = float(np.min(y))
    hi = float(np.max(y))
    n = int(np.ceil((hi - lo) / dy)) + 1
    grid = lo + np.arange(n) * dy
    idx = np.clip(np.round((y - lo) / dy).astype(int), 0, n - 1)
    env = np.full(n, -np.inf)
    np.maximum.at(env, idx, z)
    # gaps in the grid (sparse profile sections) get the neighbouring value
    seen = np.isfinite(env)
    if not seen.all():
        env[~seen] = np.interp(grid[~seen], grid[seen], env[seen])
    if nodes >= 3:
        from scipy.ndimage import median_filter

        env = median_filter(env, size=nodes, mode="nearest")
    return grid, env


def segment(grid, env, prominence=PROMINENCE, min_width=MIN_WIDTH):
    """Split the envelope into rail bodies separated by genuine valleys."""
    from scipy.signal import find_peaks

    peaks, props = find_peaks(env, prominence=prominence)
    if peaks.size == 0:
        peaks = np.array([int(np.argmax(env))])
        props = {"prominences": np.array([0.0]), "right_bases": np.array([0]),
                 "left_bases": np.array([len(env) - 1])}
    # boundaries: the lowest point between neighbouring peaks (exact for 1-D)
    bounds = [0]
    for a, b in zip(peaks[:-1], peaks[1:]):
        bounds.append(a + int(np.argmin(env[a:b + 1])))
    bounds.append(len(env) - 1)
    bodies = []
    for k, p in enumerate(peaks):
        i, j = bounds[k], bounds[k + 1]
        width = grid[j] - grid[i]
        if width < min_width:
            continue
        bodies.append(
            {
                "y_lo_m": float(grid[i]),
                "y_hi_m": float(grid[j]),
                "crown_y_m": float(grid[p]),
                "crown_z_m": float(env[p]),
                "width_m": float(width),
                "prominence_m": float(props["prominences"][k]),
                "i": int(i),
                "j": int(j),
            }
        )
    return bodies


def load_section(path_str):
    prof = load_profile(
        Path(path_str), file_format="prr", surface="rail_top",
        y_sign=1, z_sign=-1, y_offset_m=0.753,
    )
    return prof.y_m, prof.z_m


def match(prev, cur, max_dy=0.008, max_wratio=2.0):
    """Greedy matching on crown position + head width (one-to-one)."""
    pairs = []
    for a, pa in enumerate(prev):
        for b, pb in enumerate(cur):
            dy = abs(pa["crown_y_m"] - pb["crown_y_m"])
            wa, wb = pa["width_m"], pb["width_m"]
            ratio = max(wa, wb) / max(min(wa, wb), 1e-9)
            if dy < max_dy and ratio < max_wratio:
                pairs.append((dy / max_dy + (ratio - 1.0), a, b))
    pairs.sort()
    used_a, used_b, out = set(), set(), {}
    for _, a, b in pairs:
        if a in used_a or b in used_b:
            continue
        used_a.add(a)
        used_b.add(b)
        out[b] = a
    return out


def main():
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    refs = cat["profile_references"]
    right = [r for r in refs if r.get("side") == "right"]
    right.sort(key=lambda r: r["index"])
    print(f"sections: {len(right)}")

    stations = []
    tracks = []          # list of dicts
    prev_bodies = None
    for n, ref in enumerate(right):
        y, z = load_section(ref["path"])
        grid, env = envelope(y, z)
        bodies = segment(grid, env)
        s_m = float(ref["station_m"])
        stations.append({"i": n, "s_m": s_m, "n_bodies": len(bodies), "bodies": bodies,
                         "y_span_m": float(y.max() - y.min())})
        if prev_bodies is None:
            prev_track = []
            for k, b in enumerate(bodies):
                tracks.append({"id": f"T{k:02d}", "birth_s": s_m, "samples": [(n, k)]})
                prev_track.append(len(tracks) - 1)
        else:
            m = match(prev_bodies, bodies)
            cur_track = {}
            for k, b in enumerate(bodies):
                if k in m:
                    ti = prev_track[m[k]]
                    tracks[ti]["samples"].append((n, k))
                    cur_track[k] = ti
                else:
                    tracks.append({"id": f"T{len(tracks):02d}", "birth_s": s_m,
                                   "samples": [(n, k)]})
                    cur_track[k] = len(tracks) - 1
            prev_track = [cur_track[k] for k in range(len(bodies))]
        prev_bodies = bodies

    # summarise each track
    rows = []
    for t in tracks:
        ss = np.array([stations[n]["s_m"] for n, _ in t["samples"]])
        bb = [stations[n]["bodies"][k] for n, k in t["samples"]]
        cy = np.array([b["crown_y_m"] for b in bb])
        cz = np.array([b["crown_z_m"] for b in bb])
        wd = np.array([b["width_m"] for b in bb])
        rows.append({
            "id": t["id"], "n": len(ss), "s_first": float(ss[0]), "s_last": float(ss[-1]),
            "y_first": float(cy[0]), "y_last": float(cy[-1]),
            "y_min": float(cy.min()), "y_max": float(cy.max()),
            "z_mean": float(cz.mean()), "z_ptp": float(np.ptp(cz)),
            "w_first": float(wd[0]), "w_last": float(wd[-1]),
            "w_min": float(wd.min()), "w_max": float(wd.max()),
        })

    rows.sort(key=lambda r: -r["n"])
    print("\n=== tracks (by station count) ===")
    print(f"{'id':>4} {'n':>4} {'s_first':>8} {'s_last':>8} {'y_first':>9} {'y_last':>9} "
          f"{'y_min':>9} {'y_max':>9} {'z_mean':>8} {'z_ptp':>7} {'w_first':>8} {'w_last':>8} "
          f"{'w_max':>7}")
    for r in rows:
        print(f"{r['id']:>4} {r['n']:>4} {r['s_first']:>8.3f} {r['s_last']:>8.3f} "
              f"{r['y_first']*1e3:>9.1f} {r['y_last']*1e3:>9.1f} {r['y_min']*1e3:>9.1f} "
              f"{r['y_max']*1e3:>9.1f} {r['z_mean']*1e3:>8.2f} {r['z_ptp']*1e3:>7.3f} "
              f"{r['w_first']*1e3:>8.1f} {r['w_last']*1e3:>8.1f} {r['w_max']*1e3:>7.1f}")

    print("\n=== body count histogram ===")
    counts = np.array([st["n_bodies"] for st in stations])
    for v in np.unique(counts):
        print(f"  {v} bodies: {int((counts == v).sum())} stations")

    print("\n=== stations with fewest bodies ===")
    for st in sorted(stations, key=lambda s: s["n_bodies"])[:6]:
        bs = " ".join(f"[{b['y_lo_m']*1e3:.1f},{b['y_hi_m']*1e3:.1f}]" for b in st["bodies"])
        print(f"  s={st['s_m']:7.3f} n={st['n_bodies']} {bs}")

    print("\n=== probe stations ===")
    for target in (0.0, 30.0, 52.6, 53.6, 60.963, 80.278, 80.911, 82.368, 100.0, 150.0):
        st = min(stations, key=lambda s: abs(s["s_m"] - target))
        parts = " | ".join(
            f"[{b['y_lo_m']*1e3:6.1f},{b['y_hi_m']*1e3:6.1f}] crown y={b['crown_y_m']*1e3:6.1f} "
            f"z={b['crown_z_m']*1e3:+6.2f} w={b['width_m']*1e3:5.1f} prom={b['prominence_m']*1e3:4.2f}"
            for b in st["bodies"])
        print(f"  s={st['s_m']:7.3f} n={st['n_bodies']} {parts}")

    out = {"dy_m": DY, "prominence_m": PROMINENCE, "stations": stations,
           "tracks": [
               {**r, "samples": next(t["samples"] for t in tracks if t["id"] == r["id"])}
               for r in rows
           ]}
    dest = BASE / "turnout_bodies_raw.json"
    dest.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {dest}")


if __name__ == "__main__":
    main()
