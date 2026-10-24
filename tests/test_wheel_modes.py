"""The flexible-wheelset modal model: right table, right coupling, right split.

The split frequencies are the thesis's own measured numbers, so this file is what keeps the
gyroscopic term honest: if ``G`` is assembled with the wrong sign, the wrong nodal diameter,
or missing entirely, ``test_the_split_reproduces_the_measured_frequencies`` goes red.  No
mode shapes and no ANSYS are needed for any of it.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from velch.wheel_modes import (
    FORMAT,
    Mode,
    ModeError,
    ModeSet,
    assert_split_matches_thesis,
    load_modes,
    mode_table,
    thesis_crh380a_modes,
)


@pytest.fixture(scope="module")
def modes() -> ModeSet:
    return thesis_crh380a_modes()


def test_the_table_is_sorted_and_numbered(modes: ModeSet) -> None:
    numbers = modes.frequencies_hz
    assert len(modes) == 31
    assert np.all(np.diff(numbers) >= 0.0)
    assert [item.index for item in modes.modes] == list(range(1, len(modes) + 1))
    assert numbers[0] == pytest.approx(90.0)
    assert numbers[-1] == pytest.approx(1900.0)
    # A 2 km/h cutoff is what both sides use; the count must be the SDITT comment's 31.
    assert len(modes.cut(2000.0)) == 31


def test_the_gyroscopic_matrix_is_skew_and_carries_the_nodal_diameter(modes: ModeSet) -> None:
    matrix = modes.gyroscopic()
    assert matrix.shape == (len(modes), len(modes))
    assert np.allclose(matrix, -matrix.T, atol=0.0)
    diameters = modes.nodal_diameters
    # Axisymmetric modes cannot precess, so their rows must be exactly empty.
    for position, diameter in enumerate(diameters):
        if diameter == 0:
            assert not np.any(matrix[position])
    # A travelling pair couples with +-ND, not with 1 and not with ND^2.
    for left, right, diameter in modes._pairs():
        assert matrix[left, right] == pytest.approx(-float(diameter))
        assert matrix[right, left] == pytest.approx(float(diameter))
    assert len(modes._pairs()) == 12


def test_at_rest_the_modes_are_the_table(modes: ModeSet) -> None:
    """Damped natural frequencies differ from the table by ``1 - sqrt(1 - zeta^2)``.

    With ``zeta = 1e-2`` on the single-nodal-diameter modes that is 5e-5 relative — small,
    but far above float noise, so the tolerance says which quantity is being compared.
    """

    at_rest = modes.free_frequencies_hz(0.0)
    assert np.allclose(np.sort(modes.frequencies_hz), at_rest, rtol=2.0e-4, atol=1e-9)


def test_the_split_reproduces_the_measured_frequencies(modes: ModeSet) -> None:
    rows = assert_split_matches_thesis(modes, speed_kmh=200.0)
    checked = [row for row in rows if row["measured"] is not None]
    # ND2 has four modes (two travelling pairs) and ND3 four as well, so each measured pair
    # is reported twice — the table is per mode, the measurement is per degeneracy.
    distinct = {(row["nodal_diameter"], round(row["base_hz"], 1)) for row in checked}
    assert distinct == {(2, 459.7), (3, 1204.3)}
    for row in checked:
        assert row["error_hz"] <= 3.5
    two = next(row for row in checked if row["nodal_diameter"] == 2)
    three = next(row for row in checked if row["nodal_diameter"] == 3)
    # The measured numbers are 420.2 / 499.1 Hz (ND2) and 1145.4 / 1263.0 Hz (ND3).
    assert two["backward_hz"] == pytest.approx(418.57, abs=0.05)
    assert two["forward_hz"] == pytest.approx(500.83, abs=0.05)
    assert three["backward_hz"] == pytest.approx(1142.61, abs=0.05)
    assert three["forward_hz"] == pytest.approx(1265.99, abs=0.05)


def test_the_eigenvalue_solve_agrees_with_the_closed_form(modes: ModeSet) -> None:
    """Two independent paths — companion eigenproblem vs ``f ∓ ND·n`` — must not disagree.

    Without damping they must agree to float noise, which is what proves the matrices the
    solver will receive (``K + Ω²C`` and ``2ΩG``) produce the intended split.  With the
    thesis's damping they bend by ~0.06 Hz at 1.2 kHz, so that comparison gets 0.5 Hz and
    the reason is written down instead of hidden in a loose number.
    """

    at_rest = [replace(item, damping_ratio=0.0) for item in modes.modes]
    undamped = ModeSet(modes=tuple(at_rest), radius_m=modes.radius_m, source="undamped")
    spin = undamped.rotational_speed(150.0 / 3.6)
    eigenvalues = undamped.free_frequencies_hz(spin)
    for _diameter, _base, backward, forward in undamped.pair_splits_hz(spin):
        nearest_backward = eigenvalues[np.argmin(np.abs(eigenvalues - backward))]
        nearest_forward = eigenvalues[np.argmin(np.abs(eigenvalues - forward))]
        assert nearest_backward == pytest.approx(backward, abs=1e-6)
        assert nearest_forward == pytest.approx(forward, abs=1e-6)

    damped = modes.free_frequencies_hz(modes.rotational_speed(150.0 / 3.6))
    for _diameter, _base, backward, forward in modes.pair_splits_hz(
        modes.rotational_speed(150.0 / 3.6)
    ):
        nearest_backward = damped[np.argmin(np.abs(damped - backward))]
        nearest_forward = damped[np.argmin(np.abs(damped - forward))]
        assert nearest_backward == pytest.approx(backward, abs=0.5)
        assert nearest_forward == pytest.approx(forward, abs=0.5)


def test_the_split_scales_with_rotational_speed(modes: ModeSet) -> None:
    def offset_hz(speed_kmh: float, diameter: int) -> float:
        for nd, base, backward, _forward in modes.pair_splits_hz(
            modes.rotational_speed(speed_kmh / 3.6)
        ):
            if nd == diameter:
                return base - backward
        raise AssertionError(f"no ND{diameter} pair in the table")

    assert offset_hz(100.0, 2) == pytest.approx(offset_hz(200.0, 2) / 2.0, rel=1e-12)
    # 200 km/h on a 0.43 m wheel is v/(2*pi*R) = 20.563 rev/s; an ND2 mode splits by
    # ND * rev/s on each side.  Written as the physics, not as a remembered number.
    revolutions_per_second = (200.0 / 3.6) / (2.0 * np.pi * 0.43)
    assert offset_hz(200.0, 2) == pytest.approx(2.0 * revolutions_per_second, abs=1e-6)


def test_a_table_without_a_partner_is_refused() -> None:
    lonely = ModeSet(modes=(Mode(index=1, frequency_hz=200.0, damping_ratio=1e-4,
                                nodal_diameter=2),))
    with pytest.raises(ModeError, match="degenerate partner"):
        lonely.gyroscopic()


def test_a_mode_cannot_carry_impossible_numbers() -> None:
    with pytest.raises(ModeError, match="non-positive frequency"):
        Mode(index=1, frequency_hz=0.0, damping_ratio=1e-4, nodal_diameter=0)
    with pytest.raises(ModeError, match="negative damping"):
        Mode(index=1, frequency_hz=10.0, damping_ratio=-1e-4, nodal_diameter=0)
    with pytest.raises(ModeError, match="1\\.\\."):
        ModeSet(modes=(
            Mode(index=1, frequency_hz=10.0, damping_ratio=1e-4, nodal_diameter=0),
            Mode(index=3, frequency_hz=20.0, damping_ratio=1e-4, nodal_diameter=0),
        ))


def test_shapes_without_nodes_are_refused() -> None:
    with pytest.raises(ModeError, match="one node position"):
        ModeSet(
            modes=(Mode(index=1, frequency_hz=10.0, damping_ratio=1e-4, nodal_diameter=0),),
            shapes=np.zeros((1, 4, 3)),
        )


def test_the_cut_keeps_the_low_modes_and_renumbers(modes: ModeSet) -> None:
    below = modes.cut(500.0)
    # 90 + 2x108 + 2x190.1 + 320.5 + 2x360.8 + 4x459.7 + 485.2
    assert len(below) == 13
    assert below.frequencies_hz[-1] == pytest.approx(485.2)
    assert [item.index for item in below.modes] == list(range(1, 14))
    with pytest.raises(ModeError, match="cutoff"):
        modes.cut(10.0)


def test_the_file_contract_round_trips(modes: ModeSet, tmp_path: Path) -> None:
    target = modes.save(tmp_path / "wheelset_modes.json")
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["format"] == FORMAT
    assert len(payload["modes"]) == len(modes)
    assert "shapes" not in payload  # nothing pretends to have shapes it does not have
    # Frequency and nodal diameter must survive as numbers, not as formatted strings.
    replayed = load_modes(target)
    assert np.array_equal(replayed.frequencies_hz, modes.frequencies_hz)
    assert np.array_equal(replayed.nodal_diameters, modes.nodal_diameters)
    assert np.array_equal(replayed.gyroscopic(), modes.gyroscopic())
    assert replayed.source == modes.source


def test_a_file_from_another_format_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"format": "ansys-fw/0", "modes": []}), encoding="utf-8")
    with pytest.raises(ModeError, match="this build reads"):
        load_modes(path)
    with pytest.raises(ModeError, match="no wheel-mode set"):
        load_modes(tmp_path / "absent.json")


def test_the_report_lists_every_mode_and_its_partner(modes: ModeSet) -> None:
    rows = mode_table(modes)
    assert len(rows) == len(modes)
    paired = [row for row in rows if row["pair"] is not None]
    assert len(paired) == 24  # 16 single-nodal-diameter modes + 4 ND2 + 4 ND3
    assert {row["nodal_diameter"] for row in paired} == {1, 2, 3}
    assert all(rows[row["pair"]]["nodal_diameter"] == row["nodal_diameter"] for row in paired)
    assert all(rows[row["pair"]]["frequency_hz"] == row["frequency_hz"] for row in paired)


def test_the_damping_rule_follows_the_nodal_diameter(modes: ModeSet) -> None:
    for item in modes.modes:
        expected = 1.0e-3 if item.nodal_diameter == 0 else (
            1.0e-2 if item.nodal_diameter == 1 else 1.0e-4
        )
        assert item.damping_ratio == pytest.approx(expected)
