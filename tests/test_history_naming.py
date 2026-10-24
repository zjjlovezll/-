"""The header of ``history.csv`` has to name the numbers underneath it.

Two defects made this file necessary, both of them silent:

* the writer emitted analytic accelerations (``axle1_y_acc_m_per_s2``) that
  :func:`velch.io.history.classify` did not know, so the file this build produced could not be read
  back by its own reader — one unclassifiable column aborts the whole read;
* body columns were numbered from zero (``axle0_y_m``, ``bogie0_z_m``) while the contact columns on
  the same axle were numbered from one (``axle1_left_normal_n``), and the archive, the docs and the
  UI label table are all one-based.  Pairing a body channel with its contact was off by one, and the
  numbers stayed plausible.

Neither shows up as a crash, so the assertions below are about the *whole* header rather than about
a few columns somebody remembered to list.
"""

from __future__ import annotations

import json
from pathlib import Path

from velch.io.history import Channel, channel_names, classify, read_history
from velch.vehicle import load_vehicle_case
from velch.vehicle_solver import (
    _ACCELERATION_SUFFIX_BY_AXIS,
    _acceleration_channels,
    _acceleration_name,
    _column_names,
    _column_prefix,
    save_vehicle_result,
    simulate_vehicle,
    VehicleDynamics,
)

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/vehicle_v2/case.json"
VEHICLES = Path(__file__).resolve().parents[1] / "vehicles"
AXLE_BOX_VEHICLE = VEHICLES / "CRH380A_M_axlebox.json"


def test_acceleration_channels_have_units_and_a_kind_of_their_own() -> None:
    assert classify("axle1_y_acc_m_per_s2") == Channel("axle1_y_acc_m_per_s2", "m/s^2",
                                                       "acceleration")
    assert classify("carbody_roll_acc_rad_per_s2") == Channel(
        "carbody_roll_acc_rad_per_s2", "rad/s^2", "acceleration")
    # The pre-existing rules must not be shadowed by the new ones.
    assert classify("axle1_y_m_per_s").unit == "m/s"
    assert classify("axle1_y_m").kind == "state"


def test_the_registry_classifies_itself_and_contains_the_accelerations() -> None:
    every = channel_names()
    assert "axle1_y_acc_m_per_s2" in every
    assert "carbody_z_acc_m_per_s2" in every
    for name in every:
        assert classify(name).name == name
    accelerations = channel_names(kind="acceleration")
    assert accelerations
    assert all(name.endswith(("_acc_m_per_s2", "_acc_rad_per_s2")) for name in accelerations)


def test_a_written_history_reads_back_with_every_column(tmp_path: Path) -> None:
    case = load_vehicle_case(EXAMPLE)
    result = simulate_vehicle(case)
    history_path, _manifest = save_vehicle_result(case, result, tmp_path)
    table = read_history(history_path)  # raises HistoryError on the first unknown column

    header = history_path.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert set(table.ordering) == set(header)
    assert result.accelerations is not None
    assert result.accelerations.shape[1] == len(result.acceleration_names)
    written = [name for name in header if name.endswith(("_acc_m_per_s2", "_acc_rad_per_s2"))]
    assert written == list(result.acceleration_names)


def test_the_written_header_is_numbered_from_one(tmp_path: Path) -> None:
    case = load_vehicle_case(EXAMPLE)
    result = simulate_vehicle(case)
    history_path, _ = save_vehicle_result(case, result, tmp_path)
    header = history_path.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert not [name for name in header if name.startswith(("axle0", "bogie0"))]
    names = list(_column_names(case))
    assert {"axle1_y_m", "axle4_y_m", "bogie1_z_m", "bogie2_z_m", "carbody_z_m"} <= set(names)
    contacts = [name for name in header if name.endswith("_normal_n")]
    assert contacts, "the fixture should produce contact columns"
    for axle in range(1, 5):
        assert any(name.startswith(f"axle{axle}_") for name in contacts)


def test_acceleration_rows_line_up_with_the_state_columns() -> None:
    """The rows and the names come from two walks; they have to agree element for element."""

    case = load_vehicle_case(EXAMPLE)
    dynamics = VehicleDynamics(case)
    channels = _acceleration_channels(dynamics)
    from_channels = [f"{_column_prefix(body)}_{_ACCELERATION_SUFFIX_BY_AXIS[axis]}"
                     for _index, body, axis in channels]
    from_states = [name for name in (_acceleration_name(state)
                                     for state in _column_names(case)) if name]
    assert from_channels == from_states
    # The only coordinate intentionally left without a channel: the unsprung spin.
    assert all(state.endswith("_spin_rad") for state in _column_names(case)
               if _acceleration_name(state) is None)


def test_an_axle_box_rides_the_wheelset_axle_it_is_labelled_with() -> None:
    if not AXLE_BOX_VEHICLE.is_file():
        raise AssertionError(f"the axle-box vehicle is missing: {AXLE_BOX_VEHICLE}")
    raw = json.loads(AXLE_BOX_VEHICLE.read_text(encoding="utf-8"))
    bodies = {body["id"]: body for body in raw["topology"]["bodies"]}
    wheelset_axles = {body["axle"] for body in bodies.values() if body["kind"] == "wheelset"}
    box_axles = {(body_id, body["axle"]) for body_id, body in bodies.items()
                 if body["kind"] == "axlebox"}
    assert {axle for _id, axle in box_axles} <= wheelset_axles, sorted(box_axles)
    assert 0 in wheelset_axles and 0 in {axle for _id, axle in box_axles}

    class _Body:
        def __init__(self, kind: str, axle: int, bogie: int | None = None, name: str = "") -> None:
            self.kind, self.axle, self.bogie, self.id = kind, axle, bogie, name

    assert _column_prefix(_Body("wheelset", 0)) == "axle1"
    assert _column_prefix(_Body("bogie", 0, 0)) == "bogie1"
    assert _column_prefix(_Body("axlebox", 3, name="axlebox4R")) == "axle4_box_right"
