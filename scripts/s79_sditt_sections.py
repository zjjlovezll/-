"""Draw the SDITT single-body turnout sections and report where each one's top surface sits.

SDITT keeps one rail line per file family (stock, switch, wing, point) and gives each line a
mileage table of single-body sections.  The sections already carry the design lowering: the blade
at 3 mm width has its top about 15 mm below the running surface, and by 72 mm it is level with it.
That is why the layout needs no separate z-offset table -- and why re-introducing one here would be
writing the truth twice.

Recompute::

    cd F:/ai道岔状态反演辨识/Velch
    PYTHONPATH=src python -X utf8 scripts/s79_sditt_sections.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(r"G:\研究生\SDITT-RW-FT-250728\SDITT-RW-FT-250728\WRProfile-07(009)-1_18")

SECTIONS = (
    ("zjg-3", "07(009)-zjg-20200418/07(009)-zjg-20200418-3.txt"),
    ("zjg-30", "07(009)-zjg-20200418/07(009)-zjg-20200418-30.txt"),
    ("zjg-72", "07(009)-zjg-20200418/07(009)-zjg-20200418-72.txt"),
    ("qjbg-72", "07(009)-qjbg-20200418/07(009)-qjbg-20200418-72.txt"),
    ("cxg-12.5", "07(009)-cxg-20200422/07(009)-cxg-20200422-12.5.txt"),
)


def read_section(path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = np.loadtxt(path, comments="#")
    return data[:, 0], data[:, 1]


def top_surface_mm(y: np.ndarray, z: np.ndarray) -> float:
    """Highest point of the running surface, in mm below z = 0 (z grows downward in these files)."""
    return float(np.min(z)) * 1e3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="../scratch/s79_sditt_sections.png")
    options = parser.parse_args()

    figure, axes = plt.subplots(1, 2, figsize=(13, 5))
    print(f"{'section':<10}{'points':>7}{'y_lo_mm':>10}{'y_hi_mm':>10}{'z_min_mm':>10}{'z_max_mm':>10}")
    for name, relative in SECTIONS:
        path = ROOT / relative
        if not path.exists():
            print(f"{name:<10} missing {relative}")
            continue
        y, z = read_section(path)
        print(
            f"{name:<10}{y.size:7d}{y.min()*1e3:10.2f}{y.max()*1e3:10.2f}"
            f"{z.min()*1e3:10.2f}{z.max()*1e3:10.2f}"
        )
        axes[0].plot(y * 1e3, z * 1e3, linewidth=1.0, label=name)
        order = np.argsort(y)
        axes[1].plot(y[order] * 1e3, z[order] * 1e3, linewidth=1.0, label=name)

    axes[0].set_xlim(-60, 120)
    axes[0].set_ylim(-20, 30)
    axes[1].set_xlim(-45, 10)
    axes[1].set_ylim(-5, 25)
    for axis, title in zip(axes, ("SDITT sections: full view", "gauge corner / crown")):
        axis.grid(alpha=0.3)
        axis.set_xlabel("y (mm)")
        axis.set_ylabel("z (mm, downward positive)")
        axis.legend(fontsize=7)
        axis.set_title(title)
    figure.tight_layout()
    figure.savefig(options.out, dpi=130)
    plt.close(figure)
    print(f"wrote {options.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
