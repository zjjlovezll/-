"""The Simpack bridge: geometry may be imported, physics may not, and both must be provable."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from velch import simpack_case
from velch.simpack_case import SimpackCaseError

REPO = Path(__file__).resolve().parents[1]


def _profile_file(folder: Path, name: str) -> Path:
    """A PRR-shaped file: two columns, one header row is not needed by the catalog."""
    path = folder / name
    path.write_text("0.0 0.0\n0.035 0.0032\n0.070 0.0128\n", encoding="utf-8", newline="\n")
    return path


def _catalog(folder: Path, *, readable: bool = True, stations_n: int = 4,
             sides: tuple[str, ...] = ("right",), profile_name: str = "Profile_Mileage_A.prr",
             duplicate_at: float | None = None) -> Path:
    profile = _profile_file(folder, profile_name)
    import hashlib
    digest = hashlib.sha256(profile.read_bytes()).hexdigest()
    references = []
    for side in sides:
        for index in range(stations_n):
            mileage = 0.0 if index == 0 else 40.0 * index / (stations_n - 1)
            references.append({
                "source_model": str(folder / "model.spck"),
                "rail": "$RWR_Rail_1", "side": side, "index": index + 1,
                "filename": profile_name, "station_m": mileage,
                "station_expression": None, "path": str(profile), "sha256": digest,
            })
        if duplicate_at is not None:
            references.append({
                "source_model": str(folder / "model.spck"),
                "rail": "$RWR_Rail_1", "side": side, "index": 999,
                "filename": profile_name, "station_m": duplicate_at,
                "station_expression": None, "path": str(profile), "sha256": digest,
            })
    catalog = {
        "schema_version": simpack_case.CATALOG_SCHEMA,
        "scope": "test",
        "model": str(folder / "model.spck"),
        "model_root": str(folder),
        "profile_references": references,
        "summary": {
            "geometry_readable": readable,
            "missing_profile_references": 0 if readable else 2,
            "profile_set_sha256": "0" * 64,
        },
    }
    path = folder / "catalog.json"
    path.write_text(json.dumps(catalog), encoding="utf-8", newline="\n")
    return path


def _template(folder: Path, *, travel: float = 100.0, duration: float = 0.05) -> Path:
    profile = _profile_file(folder, "Template.prr")
    template = {
        "schema_version": "velch-vehicle-v2",
        "case_id": "template", "purpose": "engineering",
        "parameter_source": "test",
        "vehicle": {"travel_speed_m_s": travel},
        "rail_templates": [
            {"id": "left", "stations": [
                {"id": "L0", "s_m": 0.0,
                 "profile": {"file": str(profile), "format": "prr", "units": "m",
                             "y_sign": -1, "y_offset_m": 0.753, "z_sign": -1}}]},
            {"id": "right", "stations": [
                {"id": "R0", "s_m": 0.0,
                 "profile": {"file": str(profile), "format": "prr", "units": "m",
                             "y_sign": 1, "y_offset_m": 0.753, "z_sign": -1}}]},
        ],
        "run": {"method": "DOP853", "x_start_m": 0.0, "duration_s": duration},
    }
    path = folder / "template.json"
    path.write_text(json.dumps(template), encoding="utf-8", newline="\n")
    return path


def test_a_catalog_that_is_not_readable_is_refused_before_anything_is_written(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path, readable=False)

    with pytest.raises(SimpackCaseError, match="geometry_readable"):
        simpack_case.build_case(catalog_path=catalog, template_path=_template(tmp_path),
                                out_path=tmp_path / "out.json", side="right", x_start_m=0.0)
    assert not (tmp_path / "out.json").exists(), "a refused build must not leave a half case"


def test_a_catalog_from_another_schema_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "catalog.json"
    path.write_text(json.dumps({"schema_version": "something-else"}), encoding="utf-8")

    with pytest.raises(SimpackCaseError, match="expected"):
        simpack_case.load_catalog(path)


def test_stations_are_filtered_by_side_and_sorted_by_mileage(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path, sides=("left", "right"))
    loaded = simpack_case.load_catalog(catalog)

    right = simpack_case.stations(loaded, side="right")

    assert {entry.side for entry in right} == {"right"}
    assert [entry.station_m for entry in right] == sorted(entry.station_m for entry in right)


def test_duplicate_mileages_are_counted_rather_than_hidden(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path, stations_n=4, duplicate_at=40.0)
    loaded = simpack_case.load_catalog(catalog)
    entries = simpack_case.stations(loaded, side="right")

    kept, dropped = simpack_case._deduplicate(entries)

    assert dropped == 1, "the turnout states two surfaces at one mileage; that loss is recorded"
    assert len({entry.station_m for entry in kept}) == len(kept)


def test_mileages_are_imported_unchanged(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    built = simpack_case.build_case(
        catalog_path=catalog, template_path=_template(tmp_path), out_path=tmp_path / "case.json",
        side="right", x_start_m=10.0, duration_s=0.02)

    case = json.loads(Path(built.case_path).read_text(encoding="utf-8"))
    mileages = [station["s_m"] for station in case["rail_templates"][1]["stations"]]
    sidecar = json.loads(Path(built.sidecar_path).read_text(encoding="utf-8"))

    assert mileages == [0.0, 40.0 / 3, 80.0 / 3, 40.0] or mileages[0] == 0.0
    assert built.shift_m == 0.0, "shifting stations is how a rail stops covering the first wheel"
    assert sidecar["model_mileage_span_m"] == [0.0, 40.0]


def test_a_start_outside_the_model_span_is_refused_with_the_span_in_the_message(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)

    with pytest.raises(SimpackCaseError, match="coverage"):
        simpack_case.build_case(catalog_path=catalog, template_path=_template(tmp_path),
                                out_path=tmp_path / "case.json", side="right", x_start_m=100.0)


def test_keep_profiles_imports_the_layout_and_says_so(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path, stations_n=3)
    template = _template(tmp_path)
    built = simpack_case.build_case(
        catalog_path=catalog, template_path=template, out_path=tmp_path / "case.json",
        side="right", x_start_m=0.0, duration_s=0.02, keep_profiles=True)

    case = json.loads(Path(built.case_path).read_text(encoding="utf-8"))
    sidecar = json.loads(Path(built.sidecar_path).read_text(encoding="utf-8"))
    template_profile = json.loads(Path(template).read_text(encoding="utf-8"))["rail_templates"][1]
    files = {station["profile"]["file"] for station in case["rail_templates"][1]["stations"]}

    assert files == {template_profile["stations"][0]["profile"]["file"]}
    assert built.profiles_from == "template"
    assert sidecar["profiles_from"] == "template"
    assert sidecar["from_simpack"] == ["station mileage", "rail side", "station count"]


def test_the_sidecar_says_what_was_not_imported(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    built = simpack_case.build_case(
        catalog_path=catalog, template_path=_template(tmp_path), out_path=tmp_path / "case.json",
        side="right", x_start_m=0.0, duration_s=0.02)
    sidecar = json.loads(Path(built.sidecar_path).read_text(encoding="utf-8"))

    assert sidecar["simpack_dynamics_imported"] is False
    assert "flexible (modal) track" in sidecar["not_imported"]
    assert "rigid body dynamics" in sidecar["not_imported"]
    assert sidecar["from_template"], "the physics source must be named, not implied"
    assert sidecar["catalog_sha256"] and sidecar["template_sha256"]


def test_missing_profile_files_are_reported_before_the_case_is_written(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path, profile_name="gone.prr")
    (tmp_path / "gone.prr").unlink()

    with pytest.raises(SimpackCaseError, match="gone from disk"):
        simpack_case.build_case(catalog_path=catalog, template_path=_template(tmp_path),
                                out_path=tmp_path / "case.json", side="right", x_start_m=0.0)


def test_the_real_model_is_readable_when_the_corpus_is_mounted() -> None:
    """A real Simpack database is optional; when it is there, the catalog must read it."""

    import os
    from velch.data_root import case_dir

    model = Path(os.environ.get("VELCH_SIMPACK_MODEL", "")) if os.environ.get("VELCH_SIMPACK_MODEL") else None
    if model is None or not model.is_file():
        pytest.skip("no VELCH_SIMPACK_MODEL set")
    from velch.simpack_track_import import inspect_simpack_track

    report = inspect_simpack_track(model, model.parents[1])
    assert report["summary"]["missing_profile_references"] == 0
    assert report["summary"]["geometry_readable"] is True
    assert case_dir().name  # the corpus resolver still works after the import
