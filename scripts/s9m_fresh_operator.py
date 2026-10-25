"""Run the 8x8 band operator against a clean work directory.

``scripts/s9m_band_matrix.py`` resumes from ``matrix.json`` and reuses the
``out_p**`` run directories underneath it, so after the B027 axle-box fix the
cached operator would be silently reused (reviewer D7: the cache key carries no
protocol fingerprint).  This wrapper points every module at a fresh directory so
all eight probes and the test pair are measured again on the fixed model.

Run:  python -X utf8 scripts/s9m_fresh_operator.py
"""

from __future__ import annotations

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import s9m_band_matrix as s9m  # noqa: E402

FRESH = pathlib.Path(r"F:\velch_tmp\s9m_fixed")


def main() -> int:
    FRESH.mkdir(parents=True, exist_ok=True)
    s9m.WORK = FRESH
    s9m.s9k.WORK = FRESH
    s9m.s9l.WORK = FRESH
    print(f"work directory: {FRESH} (cache cleared by construction)")
    return s9m.main()


if __name__ == "__main__":
    raise SystemExit(main())
