"""Multi-body rail contact: one wheel, several rail heads on the same side.

A turnout cross-section carries a stock rail and a switch rail (or a wing rail
and a point rail) on one side of the gauge. Evaluating the merged profile lets
the single contact point jump between the heads; each body has to be searched on
its own profile and the wheel force summed.
"""
import numpy as np

from velch.contact import ContactGeometry, ContactResponse, merge_contact_responses
from velch.profiles import GraphProfile, ProfileSeries, Station
from velch.vehicle import RailBody


def _profile(crown_z_m: float) -> GraphProfile:
    y = np.linspace(0.70, 0.80, 11)
    z = crown_z_m - 40.0 * (y - 0.75) ** 2
    return GraphProfile(y, z, "0" * 64, "synthetic")


def _geometry(penetration_m: float, y_m: float = 0.75) -> ContactGeometry:
    return ContactGeometry(y_m, 0.43, 0.0, penetration_m,
                           0.0, 1.0, 1.0, 0.0, 0.0, -0.43, 0.0)


def _series(*stations_m: float) -> ProfileSeries:
    return ProfileSeries([Station(s, _profile(0.0), f"p{s}") for s in stations_m])


def test_merge_sums_forces_and_reports_the_deepest_geometry() -> None:
    shallow = ContactResponse(True, _geometry(0.0001, 0.72), normal_force_n=20_000.0,
                              wheel_force_z_n=20_000.0, longitudinal_force_n=600.0)
    deep = ContactResponse(True, _geometry(0.0004, 0.76), normal_force_n=60_000.0,
                           wheel_force_z_n=60_000.0, longitudinal_force_n=1_800.0)
    merged = merge_contact_responses([shallow, deep])
    assert merged.active
    assert merged.normal_force_n == 80_000.0
    assert merged.wheel_force_z_n == 80_000.0
    assert merged.longitudinal_force_n == 2_400.0
    assert merged.geometry is deep.geometry


def test_merge_of_inactive_contacts_is_inactive() -> None:
    merged = merge_contact_responses([ContactResponse(False, None), ContactResponse(False, None)])
    assert not merged.active
    assert merged.normal_force_n == 0.0


def test_body_is_active_only_inside_its_mileage_window() -> None:
    body = RailBody("point", _series(79.0, 80.0, 81.0), 79.0, 81.0)
    assert body.active_at(80.0)
    assert not body.active_at(78.999)
    assert not body.active_at(81.001)


def test_body_outside_its_station_range_is_not_active() -> None:
    body = RailBody("point", _series(79.0, 81.0))
    assert body.active_at(80.0)
    # Covered by the open window but not by the stored stations.
    assert not body.active_at(76.0)


def test_lateral_gate_rejects_a_head_outside_the_tread_band() -> None:
    gated = RailBody("point", _series(79.0, 81.0), y_window_m=(0.736, 0.800))
    assert gated.accepts_contact_y(0.740)
    assert not gated.accepts_contact_y(0.7236)   # crown still 39 mm inboard
    ungated = RailBody("main", _series(79.0, 81.0))
    assert ungated.accepts_contact_y(0.7236)


def test_body_attribution_keeps_the_incumbent_until_it_unloads() -> None:
    """Sticky handover: no jump while the loaded head still carries the wheel."""
    from velch.vehicle_solver import VehicleDynamics

    class _Run:
        body_hysteresis = True

    class _Case:
        run = _Run()

    dynamics = VehicleDynamics.__new__(VehicleDynamics)
    dynamics.case = _Case()
    dynamics.BODY_SWITCH_MARGIN_M = 2.0e-5
    dynamics.BODY_SWITCH_RELEASE_M = 5.0e-5
    dynamics._active_body = {}

    def response(p: float, y: float) -> tuple:
        geometry = _geometry(p, y)
        return (None, geometry, ContactResponse(True, geometry, normal_force_n=1.0))

    wing = response(3.0e-4, 0.776)
    point_shallow = response(1.0e-4, 0.738)
    kept = dynamics._attribute_bodies(0, [("main", wing[1], wing[2]),
                                          ("point", point_shallow[1], point_shallow[2])])
    assert kept[0][0] == "main" and len(kept) == 1

    # The wing rail has unloaded and the point rail is deeper: hand over.
    unloaded = response(1.0e-5, 0.776)
    deep_point = response(4.0e-4, 0.742)
    switched = dynamics._attribute_bodies(0, [("main", unloaded[1], unloaded[2]),
                                              ("point", deep_point[1], deep_point[2])])
    assert switched[0][0] == "point"
