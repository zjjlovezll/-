"""Tests for the modal exchange file's contract, including the shared-block limitation."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

from velch.track_models import load_modal_track


def _payload(rail_ids: list[str], modes: int = 2, stations: int = 5) -> dict:
    grid = list(np.linspace(0.0, 1.0, stations))
    shapes = {
        rail_id: {
            "station_m": grid,
            "phi_y": [[0.0] * stations for _ in range(modes)],
            "phi_z": [[float(np.cos(math.pi * (i + 1) * s / 2.0)) for s in grid]
                      for i in range(modes)],
        }
        for rail_id in rail_ids
    }
    return {
        "schema_version": "velch-modal-track-v1",
        "modes": [
            {"id": f"m{i}", "modal_mass_kg": 1.0, "frequency_hz": 40.0 + 10.0 * i,
             "damping_ratio": 0.02}
            for i in range(modes)
        ],
        "rail_shapes": shapes,
    }


def test_load_accepts_matching_ids(tmp_path: Path) -> None:
    path = tmp_path / "modes.json"
    path.write_text(json.dumps(_payload(["left", "right"])), encoding="utf-8")
    modal = load_modal_track(path, ["left", "right"])
    assert modal.mode_count == 2
    assert modal.stiffness_n_m.shape == (2,)


def test_shared_block_limitation_is_named_in_the_error(tmp_path: Path) -> None:
    path = tmp_path / "modes.json"
    path.write_text(json.dumps(_payload(["left", "right"])), encoding="utf-8")
    with pytest.raises(ValueError) as excinfo:
        load_modal_track(path, ["axle1_left", "axle1_right"])
    message = str(excinfo.value)
    assert "single set of modal coordinates" in message
    assert "layered" in message


def test_bad_schema_is_rejected(tmp_path: Path) -> None:
    payload = _payload(["left"])
    payload["schema_version"] = "something-else"
    path = tmp_path / "modes.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_modal_track(path, ["left"])


def test_non_positive_frequency_is_rejected(tmp_path: Path) -> None:
    payload = _payload(["left"])
    payload["modes"][0]["frequency_hz"] = 0.0
    path = tmp_path / "modes.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_modal_track(path, ["left"])
