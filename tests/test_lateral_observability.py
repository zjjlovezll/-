"""The lateral boundary is arithmetic before it is a simulation.

`s122` predicts where a surface feature stops being observable sideways, from the two radii measured at the
seated contact.  Those predictions decide what the four runs mean, so the arithmetic is pinned here -- including
the sharpest consequence: a 100 um bump 10 mm from the crown must leave the section's crown *exactly* where it
was, because it cannot clear the 209 um gap that separates the two surfaces there.
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s122_lateral_observability as probe  # noqa: E402


def test_a_bump_on_the_contact_line_is_visible_at_any_amplitude() -> None:
    assert probe.bump_threshold_m(0.0) == pytest.approx(0.0)


def test_the_half_width_inverts_the_threshold() -> None:
    for offset_m in (0.004, 0.006, 0.008, 0.010):
        amplitude = probe.bump_threshold_m(offset_m)
        assert probe.half_width_m(amplitude) == pytest.approx(offset_m, rel=1e-9)


def test_the_predicted_thresholds_are_what_the_document_says() -> None:
    assert probe.bump_threshold_m(0.006) * 1e6 == pytest.approx(75.1, abs=0.5)
    assert probe.bump_threshold_m(0.008) * 1e6 == pytest.approx(133.5, abs=0.5)
    assert probe.bump_threshold_m(0.010) * 1e6 == pytest.approx(208.6, abs=0.5)
    assert probe.half_width_m(100e-6) * 1e3 == pytest.approx(6.9, abs=0.05)


def test_dropping_the_wheel_curvature_makes_the_boundary_wider() -> None:
    # A tangent cone rises faster than a 1274 mm arc, so the gap it must clear is smaller: the cone-only model
    # puts the boundary further out, which is exactly what the 8 mm run is designed to separate.
    a = probe.bump_threshold_m(0.008)
    b = probe.bump_threshold_m(0.008, wheel_radius_m=float("inf"))
    assert b < a
    assert probe.half_width_m(100e-6, wheel_radius_m=float("inf")) > probe.half_width_m(100e-6)


def test_a_bump_on_the_crown_raises_the_crown_by_its_amplitude() -> None:
    section = "".join(f"{y:.6f} {z:.6f}\n" for y, z in _arc())
    baked = probe._perturbed_section(section, amplitude_m=100e-6, offset_m=0.0)
    before = _raw_crown(section)
    after = _raw_crown(baked)
    # The loader negates z for these sections, so raising the riding surface means lowering the raw minimum.
    assert before - after == pytest.approx(100e-6, abs=1e-9)


def test_a_bump_further_out_than_its_threshold_does_not_move_the_crown() -> None:
    section = "".join(f"{y:.6f} {z:.6f}\n" for y, z in _arc())
    baked = probe._perturbed_section(section, amplitude_m=100e-6, offset_m=0.010)
    # The Gaussian tail still touches the crown by a few nanometres (-4e-9 m here), which is four orders below
    # the 63.7 um static penetration -- "does not move the crown" means this, not bit-exact equality.
    assert _raw_crown(baked) == pytest.approx(_raw_crown(section), abs=1e-8)


def test_a_section_without_numbers_is_returned_unchanged() -> None:
    text = "# header only\n# no points here\n"
    assert probe._perturbed_section(text, amplitude_m=100e-6, offset_m=0.0) == text


def _arc() -> list[tuple[float, float]]:
    """A shallow parabola of the measured rail radius, 40 mm wide, crown in the middle."""
    y = np.linspace(-0.020, 0.020, 401)
    z = y**2 / (2.0 * 0.29527)
    # 0.29527 m radius about a crown at y = 0; the raw column is z with the crown at its minimum.
    return list(zip(y, z))


def _raw_crown(text: str) -> float:
    rows = [line.split() for line in text.splitlines() if line.strip()]
    z = np.array([float(row[1]) for row in rows])
    return float(z.min())
