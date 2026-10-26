"""Regressions for the defects a read-only review found on 2026-10-26.

Each test here pins one silent failure: a wrong answer that produced no error, no
warning and no failing gate.  They are grouped in one file because they share the
property that made them survive so long -- nothing downstream could tell.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from velch.model import LinearSupport
from velch.track_models import TrackKernel


class _Rail:
    mass_y_kg = 120.0
    mass_z_kg = 120.0
    template_id = "left"

    def __init__(self, support: LinearSupport, index: int = 0) -> None:
        self.support = support
        self.id = f"axle1_left{index}"


def _rails(count: int = 2) -> list[_Rail]:
    support = LinearSupport(k_y_n_m=5.0e7, c_y_n_s_m=1.0e4, k_z_n_m=4.0e8, c_z_n_s_m=2.0e4)
    return [_Rail(support, index) for index in range(count)]


@pytest.mark.parametrize("offset", [35, 38, 86])
def test_compliant_track_reads_both_axes_at_its_own_offset(offset: int) -> None:
    """The vertical row used to be the literal ``36``, so only a 35-coordinate
    vehicle had vertical support at all: on 38 or 86 coordinates the track was
    vertically free while laterally stiff -- no error, no gate failure."""

    rails = _rails()
    kernel = TrackKernel("local_compliant", rails, offset=offset)
    q = np.zeros(offset + kernel.dimension)
    v = np.zeros_like(q)
    q[offset] = 1.0e-3          # lateral coordinate of rail 0
    q[offset + 1] = 2.0e-3      # vertical coordinate of rail 0
    force = kernel.internal_force(q, v)
    assert force[0] == pytest.approx(-5.0e7 * 1.0e-3, rel=1e-12)
    assert force[1] == pytest.approx(-4.0e8 * 2.0e-3, rel=1e-12)


@pytest.mark.parametrize("offset", [35, 38, 86])
def test_compliant_track_potential_is_offset_independent(offset: int) -> None:
    rails = _rails()
    kernel = TrackKernel("local_compliant", rails, offset=offset)
    q = np.zeros(offset + kernel.dimension)
    for index in range(len(rails)):
        q[offset + 2 * index] = 1.0e-3
        q[offset + 2 * index + 1] = 2.0e-3
    expected = 0.5 * (5.0e7 * 1.0e-3**2 + 4.0e8 * 2.0e-3**2) * len(rails)
    assert kernel.potential_j(q) == pytest.approx(expected, rel=1e-12)


def test_two_channels_get_independent_random_fields() -> None:
    """Both branches of a ternary used to return the same array, so lateral and
    vertical came out perfectly correlated (corr = 1.0)."""

    from velch.irregularity_gen import generate

    track = generate(channels=("vertical", "lateral"), length_m=60.0, seed=11)
    assert np.std(track.vertical_m) > 0.0 and np.std(track.lateral_m) > 0.0
    correlation = np.corrcoef(track.vertical_m, track.lateral_m)[0, 1]
    assert abs(correlation) < 0.5, "channels must be independent random fields"
    # Same seed still reproduces, channel by channel.
    again = generate(channels=("vertical", "lateral"), length_m=60.0, seed=11)
    assert np.array_equal(track.vertical_m, again.vertical_m)
    assert np.array_equal(track.lateral_m, again.lateral_m)


def test_generate_runs_with_its_defaults() -> None:
    """The default step (0.05 m) contradicted the default shortest wavelength
    (0.05 m) and raised on every argument-free call."""

    from velch.irregularity_gen import generate

    track = generate(length_m=40.0)
    assert len(track) > 0
    assert np.std(track.vertical_m) > 0.0


def test_reach_reports_a_band_no_axle_crosses() -> None:
    """The defect that cost a debugging round: the offset was applied correctly and
    the run was still identical to no-irregularity, because no wheel reached it."""

    from velch.vehicle import _irregularity_reach

    class _Vehicle:
        travel_speed_m_s = 22.22222222222222
        bogie_half_spacing_m = 8.75
        wheelbase_m = 2.5

        @property
        def axle_offsets_m(self):
            a, b = self.bogie_half_spacing_m, self.wheelbase_m / 2.0
            return (a + b, a - b, -a + b, -a - b)

    class _Track:
        s_m = np.linspace(0.0, 60.0, 241)
        lateral_m = np.zeros(241)
        roll_rad = np.zeros(241)
        gauge_m = np.zeros(241)

        def __init__(self, band: tuple[float, float]) -> None:
            self.vertical_m = np.zeros(241)
            self.vertical_m[(self.s_m >= band[0]) & (self.s_m <= band[1])] = 3.0e-5

    run = {"x_start_m": 38.0, "duration_s": 0.25}
    # Axles run 28..33.6 and 45.5..53.6; a band at 40..41 m is never crossed.
    assert _irregularity_reach(_Vehicle(), run, _Track((40.0, 41.0)))["overlaps"] is False
    # Moving the start to 30 m puts two axles through it.
    reached = _irregularity_reach(_Vehicle(), {"x_start_m": 30.0, "duration_s": 0.25},
                                  _Track((40.0, 41.0)))
    assert reached["overlaps"] is True
    assert reached["band_m"] == [40.0, 41.0]
