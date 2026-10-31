"""The strip integral halves the null-run error but still misses the pre-gate by ten times.

Round 281's point contact made the blade's 1 mm edge look like a knife because C ~ sqrt(R*).  This model
integrates over lateral strips with the combined wheel-plus-rail gap and the local combined curvature, so the
softness of an edge is decided by geometry rather than by a size law.

Measured floors: 0.1912 (un-bumped) / 0.2008 / 0.2589 / 0.3718 with biases -0.0768 .. -0.3038 -- 1.6x
better than the point model on the null run, and still ten times the 0.02 pre-gate.

The module also pins the caveat that makes the pre-gate meaningful: it is an independent test for a
*predicted* forward, but the empirical law's null share was inverted from that same run, so the law's 0.0133
there does not mean the law passed it.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import s140_strip_stiffness as strip  # noqa: E402


def test_the_second_derivative_of_a_parabola_is_constant() -> None:
    y = np.linspace(-0.01, 0.01, 201)
    z = -(y ** 2) / (2.0 * 0.3)
    curvature = strip._second_derivative(y, z)
    middle = curvature[1:-1]
    # a crown opens downwards, so the raw second derivative is negative; _strips() takes the magnitude
    # and adds the two bodies' curvatures before inverting (round 281 got the sign wrong once already).
    assert np.allclose(middle, -1.0 / 0.3, rtol=0.02)


def test_the_force_monotonically_grows_with_penetration() -> None:
    grid = np.arange(-0.002, 0.002, 5.0e-5)
    gap = 100.0 * grid ** 2                    # a shallow crown
    strips = {"gap": gap - gap.min(), "radius": np.full(grid.shape, 0.3)}
    forces = [strip._force(strips, delta) for delta in (1e-6, 1e-5, 5e-5, 1e-4)]
    assert all(later > earlier for earlier, later in zip(forces, forces[1:]))
    assert forces[0] == pytest.approx(0.0, abs=1e-12) or forces[0] < forces[1]


@pytest.mark.corpus
def test_the_pre_gate_still_fails() -> None:
    if not strip.REPORT.exists():
        pytest.skip("the strip-stiffness test has not been produced yet")
    report = json.loads(strip.REPORT.read_text(encoding="utf-8"))
    rows = {row["route"]: row for row in report["rows"]}

    null = rows["straight_one_set"]
    assert null["floor"] > 0.10
    assert report["pre_gate_pass"] is False
    assert report["all_pass"] is False

    # 1.6x better than the point-contact model of round 281, but nowhere near the gate
    assert null["floor"] < 0.3132
    assert abs(null["bias"]) < 0.15


@pytest.mark.corpus
def test_the_verdict_names_the_solver_route() -> None:
    if not strip.REPORT.exists():
        pytest.skip("the strip-stiffness test has not been produced yet")
    report = json.loads(strip.REPORT.read_text(encoding="utf-8"))
    verdict = report["verdict"]
    assert "un-bumped run" in verdict
    assert "solver" in verdict
    assert "recovered" not in verdict and "amplitude" not in verdict
