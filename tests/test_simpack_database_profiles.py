"""Read a Simpack database's typed profile directory by basename."""
from pathlib import Path

from velch.simpack_track_import import inspect_simpack_track


def test_wheel_rail_profile_directory_is_resolved(tmp_path: Path):
    database = tmp_path / "database"
    models = database / "mbs_db_substructure"
    profiles = database / "wheel_rail_profiles"
    models.mkdir(parents=True)
    profiles.mkdir()
    (profiles / "rail.prr").write_text("profile", encoding="utf-8")
    wheelset = models / "wheelset.spck"
    wheelset.write_text(
        "rail.r.prof.file (1, $RWR_Rail_1) = 'rail.prr'\n"
        "rail.r.prof.s (1, $RWR_Rail_1) = 0.0\n",
        encoding="utf-8",
    )
    catalog = inspect_simpack_track(wheelset, database)
    assert catalog["summary"]["geometry_readable"] is True
    assert catalog["summary"]["missing_profile_references"] == 0
    assert catalog["profile_references"][0]["path"] == str((profiles / "rail.prr").resolve())
