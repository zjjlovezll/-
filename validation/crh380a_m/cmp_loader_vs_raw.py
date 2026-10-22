"""Compare what Velch's loader sees with the raw PRR upper envelope.

Both are built from the same file.  The raw envelope is ``z_up = -min(raw_z)``
binned at 1 mm; the loader returns ``GraphProfile`` (max of ``raw_z * z_sign``)
with the case's transform.  Any gap between the two curves is a defect in the
loader/transform pipeline rather than in the source data.

Usage: python cmp_loader_vs_raw.py <file.prr> [y_offset_m]
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from velch.profiles import load_profile  # noqa: E402

ROOT = Path(r"G:\研究生\动力学\CRH380A_纯刚性模型\database\database")


def parse_raw(path: Path) -> np.ndarray:
    pts: list[tuple[float, float]] = []
    inside = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s.startswith("point.begin"):
            inside = True
        elif s.startswith("point.end"):
            inside = False
        elif inside and s and not s.startswith("#"):
            f = s.split()
            if len(f) >= 2:
                try:
                    pts.append((float(f[0]), float(f[1])))
                except ValueError:
                    pass
    return np.asarray(pts, dtype=float)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    name = argv[1]
    offset = float(argv[2]) if len(argv) > 2 else 0.753
    path = next(iter(ROOT.rglob(name)), None)
    if path is None:
        raise SystemExit(f"not found: {name}")
    graph = load_profile(path, file_format="prr", surface="rail_top",
                         y_sign=1, z_sign=-1, y_offset_m=offset, z_offset_m=0.0)
    raw = parse_raw(path)
    edges = np.arange(0.715, 0.870, 0.001)
    idx = np.clip(np.digitize(raw[:, 0] + offset, edges) - 1, 0, edges.size - 2)
    top = np.full(edges.size - 1, np.inf)
    np.minimum.at(top, idx, raw[:, 1])
    print(f"=== {name}  loader nodes={graph.y_m.size}  raw pts={raw.shape[0]}")
    print(f"  {'y_abs_mm':>9s} {'loader_mm':>10s} {'raw_mm':>10s} {'diff_mm':>9s}")
    for centre in edges[:-1] + 0.0005:
        if not (0.735 <= centre <= 0.800):
            continue
        try:
            zl = float(graph.z_at(centre))
        except Exception:
            zl = float("nan")
        k = int(np.clip(np.digitize(centre, edges) - 1, 0, top.size - 1))
        zr = -top[k] if np.isfinite(top[k]) else float("nan")
        print(f"  {centre * 1e3:9.1f} {zl * 1e3:10.3f} {zr * 1e3:10.3f} "
              f"{(zl - zr) * 1e3:9.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
