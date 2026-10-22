import csv
from pathlib import Path

import pytest

from velch.gui_support import case_kind, get_value, plot_series, relocated_case, set_scalar


def test_case_editor_preserves_scalar_types():
    data = {"schema_version": "velch-vehicle-v2", "vehicle": {"speed": 2.0, "enabled": True, "count": 4}}
    assert case_kind(data) == "vehicle"
    assert set_scalar(data, ("vehicle", "speed"), "3.5") == 3.5
    assert set_scalar(data, ("vehicle", "enabled"), "false") is False
    assert set_scalar(data, ("vehicle", "count"), "5") == 5
    assert get_value(data, ("vehicle", "speed")) == 3.5
    with pytest.raises(ValueError):
        set_scalar(data, ("vehicle", "speed"), "nan")


def test_relocating_case_keeps_profile_paths(tmp_path: Path):
    source = tmp_path / "source" / "case.json"
    target = tmp_path / "other" / "case.json"
    data = {"rail_templates": [{"stations": [{"profile": {"file": "rail.csv"}}]}]}
    result = relocated_case(data, source, target)
    assert result["rail_templates"][0]["stations"][0]["profile"]["file"] == str(source.parent / "rail.csv")
    assert data["rail_templates"][0]["stations"][0]["profile"]["file"] == "rail.csv"


def test_large_result_plot_keeps_spike(tmp_path: Path):
    output = tmp_path / "history.csv"
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["time_s", "force_n"])
        for i in range(10001):
            writer.writerow([i, 1000000 if i == 6271 else 0])
    points, count = plot_series(output, "time_s", "force_n", max_points=200)
    assert count == 10001
    assert len(points) <= 200
    assert (6271, 1000000) in points
