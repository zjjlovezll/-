"""Crown measurement and seating: measure the crown, then let the solver decide.

Two separate claims are pinned here.

1. The crown comparison measures the *lowest point of the section* and its lateral position.  The
   earlier implementation sampled a fixed lateral offset, which on this model lands on the flank
   ~30 mm above the crown, so its "millimetre drop" tracked the crown's lateral shift instead of its
   height.  The measurement is patched here on purpose: inventing a realistic turnout PRR to test a
   subtraction would test the fixture, not the code.
2. Nothing geometric refuses a build any more.  Crown heights match to 0.012 mm at a window that
   cannot seat eight patches and to 0.155 mm at one that can, so "will it seat" is answered by the
   preload equilibrium — ``seat_report`` — and by nothing else.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from velch import simpack_case
from velch.simpack_case import SimpackCaseError, build_case, seat_report

CASE_DIR = Path(__file__).resolve().parent.parent / "validation" / "crh380a_m"
TEMPLATE = Path(r"F:\velch_data\validation\crh380a_m\case_A_final_law.json")


def _catalog(root: Path) -> Path:
    """A two-station catalog whose profile files exist (content is irrelevant: measurement is patched)."""

    # A real PRR: the loader validates the length unit, and a stub would test the fixture instead.
    profile = Path(json.loads(TEMPLATE.read_text(encoding="utf-8"))["rail_templates"][0]
                   ["stations"][0]["profile"]["file"])
    catalog = {
        "schema_version": simpack_case.CATALOG_SCHEMA,
        "model": {"path": str(root / "model.spck"), "sha256": "0" * 64},
        "model_root": str(root),
        "profile_references": [
            {"source_model": str(root / "model.spck"), "rail": "$RWR_Rail_1", "side": "left",
             "index": index, "filename": profile.name, "station_m": station,
             "station_expression": None, "path": str(profile), "sha256": "1" * 64}
            for index, station in enumerate((0.0, 20.0), start=1)
        ],
        "summary": {"geometry_readable": True, "missing_profile_references": 0},
    }
    path = root / "catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")
    return path


@pytest.fixture()
def template() -> Path:
    if not TEMPLATE.is_file():
        pytest.skip("corpus not mounted")
    return TEMPLATE


def _gauge_catalog(root: Path) -> Path:
    """A right-side catalog covering the 74–86 m window the gauge tests run in."""

    profile = Path(json.loads(TEMPLATE.read_text(encoding="utf-8"))["rail_templates"][1]
                   ["stations"][0]["profile"]["file"])
    catalog = {
        "schema_version": simpack_case.CATALOG_SCHEMA,
        "model": {"path": str(root / "model.spck"), "sha256": "0" * 64},
        "model_root": str(root),
        "profile_references": [
            {"source_model": str(root / "model.spck"), "rail": "$RWR_Rail_2", "side": "right",
             "index": index, "filename": profile.name, "station_m": float(station),
             "station_expression": None, "path": str(profile), "sha256": "1" * 64}
            for index, station in enumerate(range(74, 87), start=1)
        ],
        "summary": {"geometry_readable": True, "missing_profile_references": 0},
    }
    path = root / "gauge_catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8")
    return path


def test_the_crown_is_the_lowest_point_not_a_fixed_offset(tmp_path, monkeypatch):
    """A section whose crown sits 70 mm outboard still reports its own height, not the flank's."""

    calls: list[str] = []

    def fake_crown(spec):
        calls.append(spec["file"])
        # The first call measures the template; later calls are the imported stations.
        if len(calls) == 1:
            return (-29.942e-3, 0.79)
        return (-29.942e-3 + 0.012e-3, 0.86)  # 0.012 mm above the template, 70 mm outboard

    monkeypatch.setattr(simpack_case, "_crown_of", fake_crown)
    entries, _ = simpack_case._deduplicate(
        simpack_case.stations(simpack_case.load_catalog(_catalog(tmp_path)), side="left"))
    delta = simpack_case._crown_delta_mm(entries, {"file": "template.prr"})
    assert delta is not None
    worst_mm, _at_m, worst_lateral_m = delta
    assert worst_mm == pytest.approx(0.012, abs=1e-3)
    assert worst_lateral_m == pytest.approx(0.07, abs=1e-3)
    assert any(path.endswith("template.prr") for path in calls)


def test_an_unmeasurable_section_is_not_a_clean_section(tmp_path, monkeypatch):
    monkeypatch.setattr(simpack_case, "_crown_of", lambda spec: None)
    entries, _ = simpack_case._deduplicate(
        simpack_case.stations(simpack_case.load_catalog(_catalog(tmp_path)), side="left"))
    assert simpack_case._crown_delta_mm(entries, {"file": "template.prr"}) is None


def test_a_large_crown_difference_is_reported_not_refused(tmp_path, monkeypatch, template):
    """12 mm of crown difference used to abort the build; now it is a fact in the sidecar."""

    seen: list[str] = []

    def fake_crown(spec):
        seen.append(spec["file"])
        return (-29.942e-3, 0.79) if len(seen) == 1 else (-29.942e-3 - 12.0e-3, 0.79)

    monkeypatch.setattr(simpack_case, "_crown_of", fake_crown)
    built = build_case(catalog_path=_catalog(tmp_path), template_path=template,
                       out_path=tmp_path / "case.json", side="left", sample=None,
                       x_start_m=0.0, duration_s=0.05)
    summary = built.summary()
    assert summary["crown_delta_mm"]["max_abs"] == pytest.approx(-12.0, abs=1e-3)
    assert summary["crown_warning"] is not None
    assert "crown" in summary["crown_warning"]


def test_build_case_refuses_nothing_about_geometry(tmp_path, monkeypatch, template):
    """The old signature took a limit; the new one has none, and that removal is the fix."""

    source = (Path(simpack_case.__file__)).read_text(encoding="utf-8")
    assert "allow_surface_drop" not in source
    assert "max_surface_drop_mm" not in source
    assert "SURFACE_DROP" not in source


def test_seat_report_runs_the_equilibrium_and_reports_patches(tmp_path, monkeypatch, template):
    """``seats`` comes from the preload equilibrium, and a refusal carries the measurement."""

    monkeypatch.setattr(simpack_case, "_crown_of",
                        lambda spec: (-29.942e-3, 0.79))
    built = build_case(catalog_path=_catalog(tmp_path), template_path=template,
                       out_path=tmp_path / "case.json", side="left", sample=None,
                       x_start_m=0.0, duration_s=0.05)
    report = seat_report(built.summary()["case"], catalog_path=_catalog(tmp_path),
                         template_path=template, x_start_m=0.0, duration_s=0.05, side="left")
    assert set(report) >= {"case", "seats"}
    if not report["seats"]:
        assert "hung-bogie" in report["reason"] or "vertical preload" in report["reason"]
        assert "crown" in (report.get("advice") or "").lower()


def test_seat_report_advice_does_not_recommend_a_crown_based_window(tmp_path, monkeypatch, template):
    """Crowns cannot pick a window; the advice must say so instead of naming one."""

    monkeypatch.setattr(simpack_case, "_crown_of",
                        lambda spec: (-29.942e-3, 0.79))
    built = build_case(catalog_path=_catalog(tmp_path), template_path=template,
                       out_path=tmp_path / "case.json", side="left", sample=None,
                       x_start_m=0.0, duration_s=0.05)
    report = seat_report(built.summary()["case"], catalog_path=_catalog(tmp_path),
                         template_path=template, x_start_m=0.0, duration_s=0.05, side="left")
    if report["seats"]:
        pytest.skip("this window seats; the advice path is not exercised")
    advice = report["advice"]
    assert "do not predict" in advice
    assert "--keep-profiles" in advice
    assert "nearest start" not in advice


def test_build_case_refuses_a_template_without_profile_metadata(tmp_path, template):
    data = json.loads(Path(template).read_text(encoding="utf-8"))
    for station in data["rail_templates"][0]["stations"]:
        station["profile"] = {}
    broken = tmp_path / "no-profile.json"
    broken.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(SimpackCaseError):
        build_case(catalog_path=_catalog(tmp_path), template_path=broken,
                   out_path=tmp_path / "case.json", side="left", x_start_m=0.0)


def test_a_one_sided_lateral_import_is_refused_as_a_gauge_change(tmp_path, monkeypatch,
                                                                 template) -> None:
    """O008: on this model the right rail asks for +103 mm over 80–90 m and the left has no
    stations there, so importing one side "correctly" would widen the gauge by 103 mm and roll the
    vehicle onto one rail.  The gate names the number instead of letting it happen."""
    monkeypatch.setattr(simpack_case, "_crown_lateral_delta", lambda entry, template: 0.103
                        if entry.side == "right" else None)
    catalog = _gauge_catalog(tmp_path)
    out = tmp_path / "gauge_refused.json"
    with pytest.raises(simpack_case.SimpackCaseError) as caught:
        simpack_case.build_case(catalog_path=catalog, template_path=template,
                                out_path=out, side="right", rail=None, sample=None,
                                x_start_m=80.0, duration_s=0.05, keep_profiles=False,
                                import_lateral=True, allow_gauge_change=False)
    message = str(caught.value)
    assert "gauge" in message
    assert "103.0 mm" in message, message
    assert "--allow-gauge-change" in message
    assert not out.exists(), "a refused case must not be written"


def test_allow_gauge_change_lets_it_through_and_records_the_number(tmp_path, monkeypatch,
                                                                   template) -> None:
    monkeypatch.setattr(simpack_case, "_crown_lateral_delta", lambda entry, template: 0.103
                        if entry.side == "right" else None)
    catalog = _gauge_catalog(tmp_path)
    out = tmp_path / "gauge_allowed.json"
    built = simpack_case.build_case(catalog_path=catalog, template_path=template,
                                    out_path=out, side="right", rail=None, sample=40,
                                    x_start_m=80.0, duration_s=0.05, keep_profiles=False,
                                    import_lateral=True, allow_gauge_change=True)
    assert out.is_file()
    sidecar = json.loads(Path(built.sidecar_path).read_text(encoding="utf-8"))
    assert abs(sidecar["lateral_gauge_mm"]["gauge_mm"]) > 5.0
    assert sidecar["lateral_gauge_mm"]["at_m"] > 0.0
    assert sidecar["crown_lateral_m"]["shifted_stations"] == built.station_count
    payload = json.loads(out.read_text(encoding="utf-8"))
    template_rail = payload["rail_templates"][1]
    offsets = {station["profile"].get("y_offset_from") for station in template_rail["stations"]}
    assert offsets == {"simpack crown"}
    shifted = {round(station["profile"]["y_offset_m"], 9) for station in template_rail["stations"]}
    assert len(shifted) == 1 and abs(next(iter(shifted)) - 0.753) > 0.05, "patched crown moved it"


def _asymmetric_catalog(root: Path) -> Path:
    """Right rail with 13 stations, left with 2 -- the shape the real CRH380A model has."""

    import json as _json

    profile = Path(_json.loads(TEMPLATE.read_text(encoding="utf-8"))["rail_templates"][1]
                   ["stations"][0]["profile"]["file"])
    references = [
        {"source_model": str(root / "model.spck"), "rail": "$RWR_Rail_1", "side": "right",
         "index": index, "filename": profile.name, "station_m": float(station),
         "station_expression": None, "path": str(profile), "sha256": "1" * 64}
        for index, station in enumerate(range(74, 87), start=1)
    ]
    references += [
        {"source_model": str(root / "model.spck"), "rail": "$RWR_Rail_1", "side": "left",
         "index": index, "filename": profile.name, "station_m": float(station),
         "station_expression": None, "path": str(profile), "sha256": "1" * 64}
        for index, station in enumerate((0.0, 150.0), start=100)
    ]
    catalog = {
        "schema_version": simpack_case.CATALOG_SCHEMA,
        "model": {"path": str(root / "model.spck"), "sha256": "0" * 64},
        "model_root": str(root),
        "profile_references": references,
        "summary": {"geometry_readable": True, "missing_profile_references": 0},
    }
    path = root / "asymmetric_catalog.json"
    path.write_text(_json.dumps(catalog), encoding="utf-8")
    return path


def test_the_refusal_says_the_other_rail_has_no_stations(tmp_path, monkeypatch, template) -> None:
    """O008 is not "you forgot a flag": this model defines sections on one rail only (2 vs 236).

    The message has to say that, otherwise the honest fix (--keep-profiles, or a model with two
    section tables) is invisible and the reader keeps looking for the missing switch.
    """

    monkeypatch.setattr(simpack_case, "_crown_lateral_delta", lambda entry, template: 0.103
                        if entry.side == "right" else 0.0)
    with pytest.raises(simpack_case.SimpackCaseError) as caught:
        simpack_case.build_case(catalog_path=_asymmetric_catalog(tmp_path), template_path=template,
                                out_path=tmp_path / "refused.json", side="right", rail=None,
                                sample=None, x_start_m=80.0, duration_s=0.05,
                                keep_profiles=False, import_lateral=True,
                                allow_gauge_change=False)
    message = str(caught.value)
    assert "defines only 2 station(s) on the left rail" in message, message
    assert "--keep-profiles" in message
    assert "103.0 mm" in message
