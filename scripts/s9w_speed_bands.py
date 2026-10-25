"""The 6.4-12.5 m band at 200 km/h: does it move off the vehicle's own low-frequency content?

At 80 km/h the 6.4-12.5 m octave sits at 1.8-3.5 Hz, where the carbody and bogie
rigid modes live, and the band-averaged operator cannot resolve it (two of three
seeds invert to zero - `docs/BAND_CAPABILITY_2026-10-26.md` §11-12).  Speed maps
wavelength to frequency, so at 200 km/h the same band sits at 4.4-8.7 Hz.  If the
failure is "the band is buried under the body modes" then it should improve; if it
is "the band carries no information" it should not.

This script reuses the band-averaged operator measurement unchanged and only
changes the speed and the station table (the base case has rail stations 0 and
150 m, so 200 km/h for 2 s from x_start 30 m needs an extension to 400 m).

Run:  python -X utf8 scripts/s9w_speed_bands.py
"""

from __future__ import annotations

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import s9k_random_spectrum as s9k  # noqa: E402
import s9l_differential_bands as s9l  # noqa: E402
import s9s_bandaverage_operator as s9s  # noqa: E402

WORK = pathlib.Path(r"F:\velch_tmp\s9w")
SPEED_KMH = 200.0
EXTEND_TO_M = 400.0


def extend_table(base: pathlib.Path, target: pathlib.Path) -> pathlib.Path:
    """Clone every rail template's last station out to EXTEND_TO_M.

    A constant-profile straight has no geometry after 150 m, so cloning the last
    station extends the *description*, it does not invent a section.
    """
    doc = json.loads(base.read_text(encoding="utf-8"))
    for template in doc["rail_templates"]:
        stations = template.get("stations") or []
        if not stations:
            continue
        last = dict(stations[-1])
        if float(last["s_m"]) >= EXTEND_TO_M:
            continue
        stations.append({"s_m": EXTEND_TO_M, **{key: value for key, value in last.items() if key != "s_m"}})
        stations.sort(key=lambda station: float(station["s_m"]))
        template["stations"] = stations
    doc["case_id"] = "s9w_base_400m"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    return target


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    base = extend_table(s9k.BASE, WORK / "base_400m.json")
    s9k.BASE = base
    s9k.SPEED_KMH = SPEED_KMH
    s9k.DURATION_S = 2.0
    s9k.WORK = WORK
    s9l.WORK = WORK
    s9s.WORK = WORK
    print(f"speed {SPEED_KMH:.0f} km/h, base {base.name}, work {WORK}")
    return s9s.main()


if __name__ == "__main__":
    raise SystemExit(main())
