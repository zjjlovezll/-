"""The stability probe must rank growth correctly and name the mode by its own content.

The measurement these tests protect: at the seated curved state the largest real part is
+0.0009 1/s with the case's own creep and +0.0211 1/s at Kalker scale, both on a ~7.17 Hz mode
carrying 0.23 of its weight in wheelset yaw and 0.22 in wheelset lateral -- a hunting wobble, not
the divergence seen in the time integration.  An analysis that sorted by |lambda| instead of
Re(lambda), or that read the mode off the wrong rows, would report the wobble's frequency as the
cause of a growth that is actually a rigid drift.
"""

from __future__ import annotations

import importlib.util
import pathlib

import numpy as np
import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "s46_hunting_stability.py"


def _module():
    spec = importlib.util.spec_from_file_location("s46_hunting_stability", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_growth_is_ranked_by_real_part_not_by_magnitude():
    module = _module()
    # A fast oscillation at 20 Hz whose real part is negative must rank below a slow growth,
    # even though its |lambda| is far larger.
    values = np.array([-3.0 + 1.0 * 2j * np.pi * 20.0, 0.01 + 0.0j])
    vectors = np.eye(2, dtype=complex)
    rows = module.describe_modes(values, vectors, yaw_rows=[0], y_rows=[1])
    assert rows[0]["re"] == pytest.approx(0.01)
    assert rows[0]["frequency_hz"] == pytest.approx(0.0)
    assert rows[1]["re"] == pytest.approx(-3.0)
    assert rows[1]["frequency_hz"] == pytest.approx(20.0)


def test_the_mode_is_named_by_the_share_of_its_own_eigenvector():
    module = _module()
    values = np.array([0.01 + 0.0j, 0.01 + 0.0j])
    # First eigenvector lives on the yaw row, second on the lateral row.
    vectors = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=complex)
    rows = module.describe_modes(values, vectors, yaw_rows=[0], y_rows=[1])
    shares = sorted((row["yaw_share"], row["lateral_share"]) for row in rows)
    assert shares == [pytest.approx((0.0, 1.0)), pytest.approx((1.0, 0.0))]


def test_frequency_is_cycles_per_second_not_radians():
    module = _module()
    values = np.array([-1.0 + 2j * np.pi * 7.17])
    rows = module.describe_modes(values, np.eye(1, dtype=complex), yaw_rows=[0], y_rows=[])
    assert rows[0]["frequency_hz"] == pytest.approx(7.17)


def test_a_zero_real_part_is_not_stable():
    # The probe's own definition: only Re < 0 counts as stable, so the rigid drift mode measured
    # with any yaw damping (+0.0000 1/s) must not be reported as settled.
    module = _module()
    rows = module.describe_modes(np.array([0.0 + 0.0j]), np.eye(1, dtype=complex), [0], [0])
    assert rows[0]["re"] == pytest.approx(0.0)
    assert (rows[0]["re"] < 0.0) is False
