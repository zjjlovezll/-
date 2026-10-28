"""The switch zone must carry the design lowering as geometry, not as a single rail that changes shape.

Measured background (round 211, `docs/TURNOUT_LOWERING_GEOMETRY_2026-10-29.md`): in the corpus case
the diverging-side station table switches between stock, curved stock (``qjbg``), curved switch rail
(``qjg``) and point rail (``cxg``), but every profile is placed with its crown at the same height, so
only one rail exists at any mileage and the 23 mm design lowering has nowhere to live.  A real turnout
keeps both rails: the wheel rides the stock rail, and the blade takes load only after it has risen.

These tests pin the two-body build (`scripts/s52_switch_two_body.py`) and the loader path it relies on
(`rail_templates[i]["bodies"]`, `src/velch/vehicle.py:433`).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "s52_switch_two_body.py"
CASE = Path(r"F:/velch_data/validation/crh380a_m/case_diverging_R1100.json")

pytestmark = pytest.mark.corpus


def _builder():
    spec = importlib.util.spec_from_file_location("s52_switch_two_body", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    builder = _builder()
    raw, detail = builder.build(CASE, side="right")
    target = tmp_path_factory.mktemp("s52") / "case_two_body_switch.json"
    target.write_text(json.dumps(raw), encoding="utf-8")
    return builder, detail, target


def test_the_design_lowering_is_the_one_we_inject(built):
    builder, detail, _ = built
    # The schedule is the drawing's, not ours: 23 mm at the tip, zero at 7.304 m from it.
    schedule = np.array([v for _, v in detail["schedule_mm"]], dtype=float)
    distances = np.array([d for d, _ in detail["schedule_mm"]], dtype=float)
    # The drawing gives 23 / 14 / 3 / 1.375 / 0.5 / 0 mm at 0 / 0.578 / 2.889 / 5.28 / 6.569 / 7.304 m.
    assert schedule[0] == 23.0
    assert abs(float(np.interp(6.569, distances, schedule)) - 0.5) < 1.0e-9
    assert abs(float(np.interp(7.304, distances, schedule)) - 0.0) < 1.0e-9
    # Below the last datum point the interpolation must stay at zero rather than going negative.
    assert builder.lowering_mm(20.0, detail["schedule_mm"]) == 0.0


def test_the_side_now_carries_two_bodies_with_bounded_spans(built):
    _, detail, target = built

    from velch.vehicle import load_vehicle_case

    case = load_vehicle_case(target)
    rail = next(r for r in case.rails if r.template_id == "right")
    assert [body.id for body in rail.bodies] == ["right:stock", "right:blade"]
    stock, blade = rail.bodies
    # `RailBody` carries its sampled series, not a count: read the station grid off the series.
    stock_stations = len(stock.series.mileages())
    blade_stations = len(blade.series.mileages())
    assert stock_stations > 10_000
    assert 1_000 < blade_stations < 3_000
    # The blade is a candidate only where the drawing puts one.
    assert blade.s_lo_m is not None and blade.s_hi_m is not None
    assert blade.s_lo_m < blade.s_hi_m


def test_the_blade_sits_below_the_stock_rail_by_the_design_amount(built):
    _, detail, target = built

    from velch.vehicle import load_vehicle_case

    case = load_vehicle_case(target)
    rail = next(r for r in case.rails if r.template_id == "right")
    stock, blade = rail.bodies
    tip, end = detail["blade_zone_m"]

    def crown(body, s: float) -> float:
        return float(np.max(np.asarray(body.series.sample(float(s), 1.0).profile.z_m)))

    # At the tip the blade is 23 mm down; at the far end it is at full height (datum offset only).
    near_gap = (crown(stock, tip) - crown(blade, tip)) * 1.0e3
    far_gap = (crown(stock, end) - crown(blade, end)) * 1.0e3
    assert 22.5 < near_gap < 23.5
    assert abs(far_gap) < 0.2
    # And the gap grows monotonically as we walk back towards the tip, three points apart.
    gaps = [(crown(stock, s) - crown(blade, s)) * 1.0e3 for s in np.linspace(tip, end, 5)]
    assert all(later <= earlier + 1.0e-9 for earlier, later in zip(gaps, gaps[1:]))


def test_the_stock_body_no_longer_claims_a_blade_profile(built):
    _, detail, target = built

    raw = json.loads(Path(target).read_text(encoding="utf-8"))
    template = next(block for block in raw["rail_templates"] if block.get("id") == "right")
    stock = next(body for body in template["bodies"] if body["id"] == "right:stock")
    blade_names = [
        Path(st["profile"]["file"]).name
        for st in stock["stations"]
        if "-qjg-" in Path(st["profile"]["file"]).name
    ]
    assert blade_names == []
    # The stock body keeps every station, including the lateral offsets the blade zone had.
    assert len(stock["stations"]) == detail["stock_stations"]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
