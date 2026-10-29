"""The lowering-injury knob exists as a profile offset, and it is exactly additive.

Why this needs a test at all: turning a measured load rise into a lowering value is a
three-link chain -- a depth offset on the rail section, the contact that reads it, and an
estimator that divides one by the other.  The middle link was measured (round 208: +0.268 mm
in the section gives +0.268 mm in the transmitted load, 1.01 % linearity).  The *first* link
is the one that can silently do nothing: a misspelled key in a case file is accepted by every
loader in this project and simply ignored, which is exactly the failure mode this repository
has hit four times (`align_to_track`, `curve_rail_surface`, `(1 - kappa y)`, the lateral rate).

`graph_from_points` reads `z_offset_m` and adds it after the sign/scale transform
(`profiles.py:120`), so the offset is additive by construction.  This test pins that, so a
refactor that moves the offset into a later stage cannot quietly drop it, and pins that the
offset never touches the lateral coordinate -- otherwise a lowering swerve and a gauge swerve
would become indistinguishable.
"""

from __future__ import annotations

import numpy as np

from velch.profiles import load_profile


def _write_section(directory, z0: float = -0.020) -> str:
    """A shallow-crowned two-column section, y in metres across the head."""
    path = directory / "section.csv"
    y = np.linspace(-0.035, 0.035, 41)
    z = z0 + 2.5e-3 * np.cos(np.pi * y / 0.035)
    path.write_text("\n".join(f"{yi:.9f},{zi:.9f}" for yi, zi in zip(y, z)) + "\n", encoding="utf-8")
    return str(path)


def test_the_offset_is_additive_and_exact(tmp_path):
    section = _write_section(tmp_path)
    base = load_profile(section, file_format="csv", surface="rail_top", z_offset_m=0.0)
    moved = load_profile(section, file_format="csv", surface="rail_top", z_offset_m=22.6e-3)

    assert base.z_m.shape == moved.z_m.shape
    residual = moved.z_m - base.z_m
    assert np.allclose(residual, 22.6e-3, rtol=0.0, atol=1e-12), (
        "the offset must be additive everywhere, worst deviation "
        f"{np.max(np.abs(residual - 22.6e-3)):.3e} m"
    )
    assert np.array_equal(moved.y_m, base.y_m)


def test_a_negative_offset_lowers_the_rail(tmp_path):
    section = _write_section(tmp_path, z0=-0.020)
    lowered = load_profile(section, file_format="csv", surface="rail_top", z_offset_m=-13.8e-3)
    assert np.allclose(lowered.z_m, -0.020 + 2.5e-3 * np.cos(np.pi * lowered.y_m / 0.035) - 13.8e-3,
                       rtol=0.0, atol=1e-9)


def test_the_default_offset_is_the_frozen_section(tmp_path):
    section = _write_section(tmp_path)
    explicit = load_profile(section, file_format="csv", surface="rail_top", z_offset_m=0.0)
    default = load_profile(section, file_format="csv", surface="rail_top")
    assert np.array_equal(explicit.z_m, default.z_m)
    assert np.array_equal(explicit.y_m, default.y_m)
