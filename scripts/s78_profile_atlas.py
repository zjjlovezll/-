"""Draw the turnout feature sections so the shapes can be read, not guessed.

The two source folders hold SIMPACK profile files, one file per **feature section**, named by the
pinyin initials of the Chinese name (JBG = 基本轨, JG = 尖轨, XG = 心轨, YG = 翼轨, and combined
sections such as YG_DD_XG_DD).  Every file is a single rail profile; the mileage tables that place
them live in the Simpack model, not here.

This script parses each file's ``point.begin``/``point.end`` block and writes contact-sheet PNGs,
identified by the y range of each section (a single-body rail head is ~0.072 m wide; a two-body
combination spans two heads and is visible as two lobes).

Recompute::

    cd F:/ai道岔状态反演辨识/Velch
    PYTHONPATH=src python -X utf8 scripts/s78_profile_atlas.py
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

STRAIGHT = Path(
    r"G:\研究生\动力学\CRH380A_纯刚性模型\database\database\wheel_rail_profiles"
)
CURVED = Path(r"G:\研究生\道岔\道岔动力学\wheel_rail_profiles\wheel_rail_profiles")
POINT = re.compile(r"^\s*(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s*$")


def read_profile(path: Path) -> tuple[np.ndarray, np.ndarray] | None:
    """Return (y_m, z_m) of one SIMPACK profile, or None when the file has no point block."""
    y: list[float] = []
    z: list[float] = []
    inside = False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "point.begin" in line:
            inside = True
            continue
        if "point.end" in line:
            break
        if not inside or line.lstrip().startswith("!"):
            continue
        match = POINT.match(line)
        if match:
            y.append(float(match.group(1)))
            z.append(float(match.group(2)))
    if len(y) < 8:
        return None
    return np.array(y), np.array(z)


def describe(y: np.ndarray, z: np.ndarray) -> dict[str, float]:
    """Read off the numbers that tell a rail head from a two-body combination."""
    span = float(y[-1] - y[0])
    crown = float(z.max())
    # A gap in coverage wider than 20 mm means two separate bodies were drawn in one file.
    gaps = np.diff(y)
    return {
        "points": int(y.size),
        "y_min_mm": float(y[0] * 1e3),
        "y_max_mm": float(y[-1] * 1e3),
        "span_mm": span * 1e3,
        "crown_mm": crown * 1e3,
        "drop_mm": float((crown - z.min()) * 1e3),
        "max_gap_mm": float(gaps.max() * 1e3) if gaps.size else 0.0,
        "lobes": int(np.count_nonzero(gaps > 0.020)) + 1,
    }


def sheet(
    entries: list[tuple[str, np.ndarray, np.ndarray]],
    title: str,
    out: Path,
    cols: int = 6,
) -> None:
    rows = max(1, (len(entries) + cols - 1) // cols)
    figure, axes = plt.subplots(rows, cols, figsize=(cols * 2.6, rows * 2.2), squeeze=False)
    for axis in axes.ravel():
        axis.set_visible(False)
    for axis, (name, y, z) in zip(axes.ravel(), entries):
        axis.set_visible(True)
        axis.plot(y * 1e3, z * 1e3, "-", linewidth=1.2)
        info = describe(y, z)
        axis.set_title(
            f"{name}\nspan {info['span_mm']:.0f} mm  lobes {info['lobes']}  drop {info['drop_mm']:.1f} mm",
            fontsize=7,
        )
        axis.tick_params(labelsize=6)
        axis.grid(True, alpha=0.25)
        axis.set_xlabel("y (mm)", fontsize=6)
        axis.set_ylabel("z (mm)", fontsize=6)
    figure.suptitle(title, fontsize=10)
    figure.tight_layout()
    figure.savefig(out, dpi=125)
    plt.close(figure)
    print(f"{out}  ({len(entries)} sections)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="../scratch/s78")
    options = parser.parse_args()
    out = Path(options.out)
    out.mkdir(parents=True, exist_ok=True)

    for label, folder in (("straight", STRAIGHT), ("curved", CURVED)):
        if not folder.exists():
            print(f"{label}: missing {folder}")
            continue
        named: list[tuple[str, np.ndarray, np.ndarray]] = []
        mileages: list[tuple[str, np.ndarray, np.ndarray]] = []
        for path in sorted(folder.glob("*.prr")):
            stem = path.stem
            if stem.startswith("Profile_Mileage_"):
                stem = stem[len("Profile_Mileage_") :]
            parsed = read_profile(path)
            if parsed is None:
                continue
            if stem.startswith(("Rail_", "UIC", "Ri60", "S1002")):
                continue
            if stem[0].isalpha() and any(ch.isalpha() for ch in stem):
                named.append((stem, *parsed))
            else:
                mileages.append((stem, *parsed))
        print(f"\n[{label}] named feature sections: {len(named)}   mileage stations: {len(mileages)}")
        for name, y, z in named:
            info = describe(y, z)
            print(
                f"  {name:<22} pts {info['points']:5d}  y {info['y_min_mm']:+8.2f}..{info['y_max_mm']:+8.2f}  "
                f"span {info['span_mm']:7.2f} mm  crown {info['crown_mm']:+7.3f}  drop {info['drop_mm']:6.2f}  "
                f"lobes {info['lobes']}"
            )
        if named:
            sheet(named, f"{label}: named feature sections", out / f"{label}_named.png")
        if mileages:
            # Contact sheets of the mileage stations, in blocks, so the shape evolution is visible.
            block = 24
            for start in range(0, len(mileages), block):
                chunk = mileages[start : start + block]
                sheet(
                    chunk,
                    f"{label}: mileage stations {chunk[0][0]}..{chunk[-1][0]}",
                    out / f"{label}_mileage_{start:03d}.png",
                    cols=6,
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
