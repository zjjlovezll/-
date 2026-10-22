"""Tests for the measured-channel contract (sensor plan, strain->force, events)."""

from __future__ import annotations

import numpy as np
import pytest

from velch.inverse import ObservationSet, align
from velch.inverse.channels import (
    ChannelContractError,
    SensorChannel,
    SensorPlan,
    StrainCalibration,
    detect_peak_event,
    force_from_moment,
    influence_ordinate_simple_support,
    moment_from_strain,
    observed_from_measured,
    standard_turnout_plan,
    strain_channel_to_force,
)

E_STEEL = 2.1e11
I_RAIL = 3.2e-5  # 60 kg/m rail, about the vertical second moment
C_RAIL = 0.076   # neutral axis to rail foot


def test_strain_moment_force_round_trip() -> None:
    load_n = 68_000.0
    ordinate = influence_ordinate_simple_support(1.5, 2.1, 3.6)
    moment = load_n * ordinate
    strain = moment * C_RAIL / (E_STEEL * I_RAIL) / 1.0e-6
    recovered_moment = moment_from_strain(strain, youngs_modulus_pa=E_STEEL,
                                          second_moment_m4=I_RAIL,
                                          distance_to_extreme_fibre_m=C_RAIL)
    recovered_load = force_from_moment(recovered_moment, ordinate)
    assert recovered_load == pytest.approx(load_n, rel=1e-9)
    # The same path through the public converter.
    via_geometry = strain_channel_to_force(
        np.array([strain]), youngs_modulus_pa=E_STEEL, second_moment_m4=I_RAIL,
        distance_to_extreme_fibre_m=C_RAIL, influence_ordinate_m=ordinate)
    assert via_geometry[0] == pytest.approx(load_n, rel=1e-9)


def test_influence_ordinate_shape() -> None:
    assert influence_ordinate_simple_support(0.0, 1.8, 3.6) == pytest.approx(0.0)
    assert influence_ordinate_simple_support(3.6, 1.8, 3.6) == pytest.approx(0.0)
    assert influence_ordinate_simple_support(1.8, 1.8, 3.6) == pytest.approx(0.9)
    with pytest.raises(ChannelContractError):
        influence_ordinate_simple_support(1.0, 4.0, 3.6)
    with pytest.raises(ChannelContractError):
        influence_ordinate_simple_support(1.0, 1.0, 0.0)


def test_calibration_from_static_test() -> None:
    true = StrainCalibration(n_per_microstrain=1.2e4, offset_n=-800.0)
    strains = np.array([0.0, 1.0, 2.0, 5.0, 8.0])
    loads = true.force_n(strains)
    fitted = StrainCalibration.from_static_test(strains, loads, provenance="bench")
    assert fitted.n_per_microstrain == pytest.approx(1.2e4, rel=1e-9)
    assert fitted.offset_n == pytest.approx(-800.0, abs=1e-6)
    assert fitted.force_n(9.0) == pytest.approx(true.force_n(9.0), rel=1e-9)
    assert fitted.inverse(fitted.force_n(3.0)) == pytest.approx(3.0, rel=1e-9)
    with pytest.raises(ChannelContractError):
        StrainCalibration(n_per_microstrain=0.0)
    with pytest.raises(ChannelContractError):
        StrainCalibration.from_static_test([1.0], [1.0])


def test_strain_channel_to_force_prefers_calibration_and_rejects_partial_geometry() -> None:
    calibration = StrainCalibration(n_per_microstrain=9.5e3, offset_n=120.0)
    strain = np.array([1.0, 2.0, 3.0])
    by_calibration = strain_channel_to_force(strain, calibration=calibration)
    assert by_calibration == pytest.approx(calibration.force_n(strain))
    with pytest.raises(ChannelContractError):
        strain_channel_to_force(strain, youngs_modulus_pa=E_STEEL,
                                second_moment_m4=I_RAIL,
                                distance_to_extreme_fibre_m=C_RAIL)
    with pytest.raises(ChannelContractError):
        moment_from_strain(strain, youngs_modulus_pa=0.0, second_moment_m4=I_RAIL,
                           distance_to_extreme_fibre_m=C_RAIL)
    with pytest.raises(ChannelContractError):
        force_from_moment(np.array([1.0]), 0.0)


def test_standard_plan_shape_and_specs() -> None:
    plan = standard_turnout_plan()
    acceleration = plan.by_kind("acceleration")
    assert len(acceleration) == 4 * 3 + 1  # four axle boxes triaxial + rail vertical
    strain = plan.by_kind("strain")
    assert {channel.unit for channel in strain} == {"N"}
    assert {channel.name for channel in strain} == {"left_rail_foot_strain",
                                                    "right_rail_foot_strain"}
    displacement = plan.by_kind("displacement")
    assert displacement and displacement[0].unit == "m"
    specs = plan.specs()
    assert len(specs) == len(plan.channels)
    assert plan.sample_rate_hz == 5000.0
    data = plan.specs(role="data")
    assert all(spec.role == "data" for spec in data)
    assert len(data) == len(specs) - 2  # rail acceleration and displacement are checks
    with pytest.raises(ChannelContractError):
        standard_turnout_plan(axle_boxes=())
    with pytest.raises(ChannelContractError):
        SensorChannel("x", "temperature", "K", 1.0, 0.0)
    with pytest.raises(ChannelContractError):
        SensorChannel("x", "acceleration", "m/s^2", 0.0, 0.0)
    with pytest.raises(ChannelContractError):
        SensorPlan((SensorChannel("a", "acceleration", "m/s^2", 1.0, 0.0),
                    SensorChannel("a", "acceleration", "m/s^2", 1.0, 0.0)))


def test_detect_peak_event() -> None:
    time = np.linspace(0.0, 0.1, 2001)
    centre = 0.0432
    values = 60e3 + 70e3 * np.exp(-((time - centre) / 0.002) ** 2)
    event = detect_peak_event(time, values, channel="right_rail_foot_strain",
                              prominence=1e4, speed_m_s=97.2, station_at_zero_m=70.0)
    assert event.time_s == pytest.approx(centre, abs=1e-4)
    assert event.station_m == pytest.approx(70.0 + 97.2 * event.time_s, abs=1e-6)
    assert event.channel == "right_rail_foot_strain"
    assert event.amplitude > 1.2e5
    # A valley is found with direction="minimum".
    dipped = detect_peak_event(time, -values, channel="x", direction="minimum",
                               prominence=1e4)
    assert dipped.time_s == pytest.approx(centre, abs=1e-4)
    with pytest.raises(ChannelContractError):
        detect_peak_event(time, values, channel="x", prominence=1e12)
    with pytest.raises(ChannelContractError):
        detect_peak_event(time, values * np.nan, channel="x")


def test_observed_from_measured_and_event_alignment() -> None:
    plan = standard_turnout_plan(axle_boxes=(1,), include_rail_acceleration=False,
                                 include_displacement=False)
    time = np.linspace(0.0, 0.2, 1001)
    accel = 5.0 * np.sin(2.0 * np.pi * 40.0 * time)
    strain_force = 60e3 + 20e3 * np.sin(2.0 * np.pi * 40.0 * time)
    columns = {
        "axle1_box_acc_x": np.zeros_like(time),
        "axle1_box_acc_y": np.zeros_like(time),
        "axle1_box_acc_z": accel,
        "left_rail_foot_strain": strain_force,
        "right_rail_foot_strain": strain_force,
    }
    observed = observed_from_measured(time, columns, plan=plan)
    assert observed.names == ("axle1_box_acc_x", "axle1_box_acc_y", "axle1_box_acc_z",
                             "left_rail_foot_strain", "right_rail_foot_strain")

    missing = dict(columns)
    del missing["left_rail_foot_strain"]
    with pytest.raises(ChannelContractError):
        observed_from_measured(time, missing, plan=plan)

    # Anchor at a known feature, shift the prediction, and confirm the event strategy
    # recovers the offset that a naive time alignment cannot.
    specs = observed.channels
    shifted_axis = time + 0.015
    predicted = ObservationSet(specs, shifted_axis, observed.values, "s")
    naive = align(observed, predicted, "time")
    anchored = align(observed, predicted, "event",
                     event_time_s=float(time[0]) + 0.015,
                     event_anchor_s=float(time[0]))
    assert anchored.rms < naive.rms
