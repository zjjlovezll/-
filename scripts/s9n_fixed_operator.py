"""Run the operator analysis against the post-B027 measurements.

``scripts/s9n_band_operator.py`` reads ``F:\\velch_tmp\\s9m``; this wrapper points
it at the clean re-measurement in ``F:\\velch_tmp\\s9m_fixed`` so the superposition
check and both inversions are computed from the fixed model instead of the
cached pre-fix matrix (reviewer D7).

Run:  python -X utf8 scripts/s9n_fixed_operator.py
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import s9n_band_operator as s9n  # noqa: E402

FRESH = pathlib.Path(r"F:\velch_tmp\s9m_fixed")


def main() -> int:
    s9n.WORK = FRESH
    s9n.MATRIX = FRESH / "matrix.json"
    return s9n.main()


if __name__ == "__main__":
    raise SystemExit(main())
