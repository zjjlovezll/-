"""A station can carry a vertical offset, and the loader honours it.

The turnout's design geometry includes a *lowering* (降低值): the switch rail and the long point rail
are made lower than the stock rail near their tips -- 23 mm at the tip, tapering to zero over 7.3 m on
the 07(009) side.  That lowering is a design quantity, so it belongs in the station table as geometry,
not in the irregularity channel.

Measured before this test was written: the corpus case carries **no** vertical offset at all -- every
station spec has exactly ``{s_m, id, profile.{file, format, units, y_sign, z_sign, y_offset_m}}``, and
the sampled crown is flat at +0.000 mm (left) and +0.072 mm (right) from 40 m to 116 m.  So the model's
running surface is level and the design lowering is missing.  ``z_offset_m`` is the field that carries
it, ``velch.profiles.load_profile`` already applies it, and ``load_vehicle_case`` already passes it
through -- this test pins both halves so a later refactor cannot quietly drop it.

The first assertion is the load-bearing one: a 5 mm offset must move the crown by *exactly* 5 mm.  A
sign error or a missed metre/millimetre conversion would show up here; nothing else in the suite would.

Both cases are loaded once per module: this corpus is 19 001 stations per template, so one load costs
about 45 s and repeating it per test would make the gate pay for nothing.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from velch import data_root
from velch.vehicle import load_vehicle_case

pytestmark = pytest.mark.corpus

LOWERING_M = -0.005
SAMPLE_AT_M = 70.0


def _crown_mm(case, rail_index: int) -> float:
    body = case.rails[rail_index].bodies[0]
    profile = body.series.sample(SAMPLE_AT_M, 1.0).profile
    return float(np.max(np.asarray(profile.z_m, dtype=float))) * 1.0e3


@pytest.fixture(scope="module")
def plain():
    return load_vehicle_case(data_root.case_dir() / "case_diverging_R1100.json")


@pytest.fixture(scope="module")
def lowered(tmp_path_factory):
    raw = json.loads((data_root.case_dir() / "case_diverging_R1100.json").read_text(encoding="utf-8"))
    for block in raw["rail_templates"]:
        if block.get("id") != "left":
            continue
        for station in block["stations"]:
            station["profile"]["z_offset_m"] = LOWERING_M
    path = tmp_path_factory.mktemp("lowered") / "case_left_lowered.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return load_vehicle_case(path)


def test_a_station_offset_moves_the_crown_by_exactly_that_amount(plain, lowered):
    before = _crown_mm(plain, 0)
    after = _crown_mm(lowered, 0)
    assert after - before == pytest.approx(LOWERING_M * 1.0e3, abs=1.0e-9), (
        f"a {LOWERING_M * 1e3:+.1f} mm station offset moved the crown by {after - before:+.3f} mm"
    )
    # The template is shared by every axle on that side, so all four move together.
    for rail_index in range(4):
        assert _crown_mm(lowered, rail_index) - _crown_mm(plain, rail_index) == pytest.approx(
            LOWERING_M * 1.0e3, abs=1.0e-9
        )


def test_the_other_side_is_untouched(plain, lowered):
    # Lowering the left template must not move the right rail by even one bit.  An absent
    # ``z_offset_m`` and a zero one are the same code path, so the plain case also covers the
    # "no offset" case and no third load is needed.
    assert _crown_mm(lowered, 4) == _crown_mm(plain, 4)
