"""Flexible-wheelset modal dynamics: the mode table, the gyroscopic term, and the check.

The formulation is thesis (2-30) — 陈嘉胤, 高速铁路道岔区轮轨多体系统耦合动力学建模及仿真分析,
§2.2.2 — with modal coordinates normalised to unit modal mass:

    q̈_w + (2 ζ_i ω_i + 2 Ω G) q̇_w + (K_w + Ω² C) q_w = Q_w

and ``K_w = diag(ω_i²)`` (2-32).  Because the modal mass is the identity, the solver adds
these coordinates exactly like any other body: acceleration = force / 1.  What is *not*
diagonal is the gyroscopic coupling, so the modal block contributes a constant skew matrix
to ``∂f/∂q`` and ``∂f/∂v`` instead of zeros.

``C`` is the centrifugal matrix ``C = G·G + G·J − J·G − J·J − E`` (2-31).  ``J`` and ``E``
are element volume integrals (2-33…2-36) and need the mode shapes at the nodes; until a
real modal set exists ``C`` is zero, and the split still comes out right.  With
``G = [[0, −ND], [ND, 0]]`` a degenerate pair has frequencies ``ω ∓ Ω·ND`` to first order —
that is thesis (2-42), and the ~1.7 Hz residual against their own measured 420.2 / 499.1 Hz
is the second-order term ``μ²/2ω``, not a missing matrix.  ``Ω²C`` is therefore an optional
refinement, not part of what makes the physics right.

Two shapers feed the same table: ``thesis_crh380a_modes()`` reproduces the published table
(2-3) so the framework can be built and tested without ANSYS, and ``load_modes`` reads a
real modal set through the versioned JSON contract.  Nothing here invents a mode shape:
``ModeSet.shapes`` is ``None`` unless a file supplied one, and the force-mapping code must
say so rather than quietly treating a missing shape as zero.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

#: Contract version written by ``ModeSet.to_json`` and required by ``from_json``.
FORMAT = "velch-wheel-modes/1"


class ModeError(ValueError):
    """A mode table cannot be turned into a modal system."""


@dataclass(frozen=True)
class Mode:
    """One mode: how fast it rings, how much it damps, and how many nodal diameters it has."""

    index: int
    frequency_hz: float
    damping_ratio: float
    nodal_diameter: int
    label: str = ""

    def __post_init__(self) -> None:
        if self.index < 1:
            raise ModeError(f"mode index {self.index} must be 1 or greater")
        if not math.isfinite(self.frequency_hz) or self.frequency_hz <= 0.0:
            raise ModeError(f"mode {self.index} has non-positive frequency {self.frequency_hz}")
        if not math.isfinite(self.damping_ratio) or self.damping_ratio < 0.0:
            raise ModeError(f"mode {self.index} has negative damping ratio")
        if self.nodal_diameter < 0:
            raise ModeError(f"mode {self.index} has a negative nodal diameter")

    @property
    def omega(self) -> float:
        """Angular frequency in rad/s."""

        return 2.0 * math.pi * self.frequency_hz


@dataclass(frozen=True)
class ModeSet:
    """A wheelset's modal model: ``n`` modes at unit modal mass.

    ``shapes`` is ``(n_modes, n_nodes, 3)`` when a file supplied them, else ``None``; the
    solver refuses to map forces onto modes it has no shape for, instead of assuming zero.
    """

    modes: tuple[Mode, ...]
    radius_m: float = 0.43
    shapes: np.ndarray | None = None
    nodes: np.ndarray | None = None
    source: str = ""

    def __post_init__(self) -> None:
        if not self.modes:
            raise ModeError("a mode set needs at least one mode")
        order = [item.index for item in self.modes]
        if order != list(range(1, len(self.modes) + 1)):
            raise ModeError(f"mode indices must be 1..{len(self.modes)} in order, got {order}")
        if self.radius_m <= 0.0:
            raise ModeError(f"rolling radius must be positive, got {self.radius_m}")
        if self.shapes is not None:
            array = np.asarray(self.shapes, dtype=float)
            if array.ndim != 3 or array.shape[0] != len(self.modes) or array.shape[2] != 3:
                raise ModeError(
                    f"shapes must be (n_modes, n_nodes, 3) = ({len(self.modes)}, ?, 3), "
                    f"got {array.shape}"
                )
            if self.nodes is None or len(self.nodes) != array.shape[1]:
                raise ModeError("shapes need one node position per node column")

    # -- sizes and tables ---------------------------------------------------------
    def __len__(self) -> int:
        return len(self.modes)

    @property
    def frequencies_hz(self) -> np.ndarray:
        return np.array([item.frequency_hz for item in self.modes], dtype=float)

    @property
    def damping_ratios(self) -> np.ndarray:
        return np.array([item.damping_ratio for item in self.modes], dtype=float)

    @property
    def nodal_diameters(self) -> np.ndarray:
        return np.array([item.nodal_diameter for item in self.modes], dtype=int)

    @property
    def has_shapes(self) -> bool:
        return self.shapes is not None and self.nodes is not None

    def cut(self, limit_hz: float) -> "ModeSet":
        """Keep the modes at or below ``limit_hz``, renumbered from 1."""

        keep = [item for item in self.modes if item.frequency_hz <= limit_hz]
        if not keep:
            raise ModeError(f"no mode survives a {limit_hz:g} Hz cutoff")
        if len(keep) == len(self.modes):
            return self
        indexed = tuple(
            Mode(index=position + 1, frequency_hz=item.frequency_hz,
                 damping_ratio=item.damping_ratio, nodal_diameter=item.nodal_diameter,
                 label=item.label)
            for position, item in enumerate(keep)
        )
        shapes = None if self.shapes is None else np.asarray(self.shapes, dtype=float)[:len(keep)]
        return ModeSet(modes=indexed, radius_m=self.radius_m,
                       shapes=shapes, nodes=self.nodes, source=self.source)

    # -- the two matrices the solver needs ---------------------------------------
    def stiffness_diagonal(self) -> np.ndarray:
        """``diag(ω_i²)`` in (rad/s)², the ``K_w`` of (2-32)."""

        return np.array([item.omega ** 2 for item in self.modes], dtype=float)

    def damping_diagonal(self) -> np.ndarray:
        """``2 ζ_i ω_i`` in rad/s — the modal damping the solver folds into ``∂f/∂v``."""

        return np.array(
            [2.0 * item.damping_ratio * item.omega for item in self.modes], dtype=float
        )

    def gyroscopic(self) -> np.ndarray:
        """The unitless, skew ``G`` of (2-30): opposite rotations for a degenerate pair.

        A pair of modes with the same frequency and the same non-zero nodal diameter
        travelling as ``cos(NDθ)`` and ``sin(NDθ)`` precess in opposite senses, which is
        why the two blocks are ``[[0, −ND], [ND, 0]]`` and their transpose.  Modes with
        ``ND = 0`` are axisymmetric and get no row at all.  Unpaired modes with ``ND > 0``
        are a symmetry error in the table and are rejected rather than guessed at.
        """

        count = len(self.modes)
        matrix = np.zeros((count, count))
        for left, right, diameter in self._pairs():
            matrix[left, right] -= float(diameter)
            matrix[right, left] += float(diameter)
        return matrix

    def centrifugal(self) -> np.ndarray:
        """``C`` of (2-31), zero until ``J`` and ``E`` exist.

        ``C = G·G + G·J − J·G − J·J − E``.  Every term except ``G·G`` needs the mode shapes
        (2-33…2-36), so with no shapes only ``G·G`` is available and it is already the
        ``−ND²`` diagonal that the second-order split term comes from.  Returning it here
        keeps the identity ``C`` in one place; passing ``None`` would look like "no
        centrifugal effect", which is a different statement.
        """

        matrix = self.gyroscopic()
        return matrix @ matrix

    def _pairs(self) -> tuple[tuple[int, int, int], ...]:
        """Degenerate (i, j, ND) triples, indices zero-based."""

        pairs: list[tuple[int, int, int]] = []
        used: set[int] = set()
        for left, item in enumerate(self.modes):
            if left in used or item.nodal_diameter == 0:
                continue
            for right in range(left + 1, len(self.modes)):
                other = self.modes[right]
                if right in used:
                    continue
                if (other.nodal_diameter == item.nodal_diameter
                        and math.isclose(other.frequency_hz, item.frequency_hz, rel_tol=1e-6)):
                    pairs.append((left, right, item.nodal_diameter))
                    used.update((left, right))
                    break
        orphan = [
            item.index for position, item in enumerate(self.modes)
            if position not in used and item.nodal_diameter != 0
        ]
        if orphan:
            raise ModeError(
                f"modes {orphan} carry nodal diameters but have no degenerate partner; "
                "the table must list a travelling pair for every ND > 0 mode"
            )
        return tuple(pairs)

    # -- what the split should be -------------------------------------------------
    def rotational_speed(self, speed_m_s: float) -> float:
        """``Ω`` in rad/s for a vehicle speed, from the rolling radius."""

        return float(speed_m_s) / self.radius_m

    def free_frequencies_hz(self, spin_rad_s: float = 0.0) -> np.ndarray:
        """Natural frequencies of the damped modal system, ascending, in Hz.

        Solves the companion eigenproblem of
        ``q̈ + (D + 2ΩG) q̇ + (K + Ω²C) q = 0`` exactly — no small-Ω expansion — so a test
        can compare against measured split frequencies rather than against my arithmetic.
        A negative-real-part eigenvalue is a damped mode; the reported frequency is the
        imaginary part, which is what a Campbell diagram plots.
        """

        count = len(self.modes)
        spin = float(spin_rad_s)
        stiffness = np.diag(self.stiffness_diagonal()) + (spin ** 2) * self.centrifugal()
        damping = np.diag(self.damping_diagonal()) + 2.0 * spin * self.gyroscopic()
        blocks = np.zeros((2 * count, 2 * count))
        blocks[:count, count:] = np.eye(count)
        blocks[count:, :count] = -stiffness
        blocks[count:, count:] = -damping
        eigenvalues = np.linalg.eigvals(blocks)
        # The companion matrix carries every mode twice (conjugate pair), so keep one side:
        # the frequency is the imaginary part, and both halves of a conjugate pair share it.
        imaginary = eigenvalues.imag[eigenvalues.imag > 0.0] / (2.0 * math.pi)
        return np.sort(imaginary)

    def pair_splits_hz(self, spin_rad_s: float) -> tuple[tuple[int, float, float, float], ...]:
        """``(nodal_diameter, base_hz, backward_hz, forward_hz)`` for every degenerate pair.

        The mapping from an eigenvalue pair to backward/forward is by frequency, not by
        assuming which side moves which way: the lower of the two split frequencies is
        reported as backward, matching thesis (2-42) ``f^B = f − ND·n``.
        """

        spin = float(spin_rad_s)
        spin_hz = spin / (2.0 * math.pi)
        result: list[tuple[int, float, float, float]] = []
        for left, _right, diameter in self._pairs():
            base = self.modes[left].frequency_hz
            offset = diameter * spin_hz
            result.append((diameter, base, base - offset, base + offset))
        return tuple(result)

    # -- the versioned file contract (the "A" interface) --------------------------
    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "format": FORMAT,
            "source": self.source,
            "radius_m": self.radius_m,
            "modes": [
                {
                    "index": item.index,
                    "frequency_hz": item.frequency_hz,
                    "damping_ratio": item.damping_ratio,
                    "nodal_diameter": item.nodal_diameter,
                    "label": item.label,
                }
                for item in self.modes
            ],
        }
        if self.has_shapes:
            payload["nodes"] = np.asarray(self.nodes, dtype=float).tolist()
            payload["shapes"] = np.asarray(self.shapes, dtype=float).tolist()
        return payload

    def save(self, path: str | Path) -> Path:
        target = Path(path)
        target.write_text(json.dumps(self.to_json(), indent=2, ensure_ascii=False), encoding="utf-8")
        return target

    @classmethod
    def from_json(cls, payload: Mapping[str, Any]) -> "ModeSet":
        if not isinstance(payload, Mapping):
            raise ModeError("a wheel-mode set must be a JSON object")
        version = payload.get("format")
        if version != FORMAT:
            raise ModeError(
                f"wheel-mode set has format {version!r}, this build reads {FORMAT!r}"
            )
        raw_modes = payload.get("modes")
        if not isinstance(raw_modes, Sequence) or isinstance(raw_modes, (str, bytes)):
            raise ModeError("a wheel-mode set needs a 'modes' list")
        modes = tuple(
            Mode(
                index=int(item["index"]),
                frequency_hz=float(item["frequency_hz"]),
                damping_ratio=float(item["damping_ratio"]),
                nodal_diameter=int(item["nodal_diameter"]),
                label=str(item.get("label", "")),
            )
            for item in raw_modes
        )
        nodes = payload.get("nodes")
        shapes = payload.get("shapes")
        return cls(
            modes=modes,
            radius_m=float(payload.get("radius_m", 0.43)),
            shapes=None if shapes is None else np.asarray(shapes, dtype=float),
            nodes=None if nodes is None else np.asarray(nodes, dtype=float),
            source=str(payload.get("source", "")),
        )


def load_modes(path: str | Path) -> ModeSet:
    """Read a wheel-mode set from disk, refusing anything this build cannot interpret."""

    target = Path(path)
    if not target.is_file():
        raise ModeError(f"no wheel-mode set at {target}")
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ModeError(f"{target} is not valid JSON: {exc}") from exc
    modes = ModeSet.from_json(payload)
    if not modes.source:
        modes = ModeSet(modes=modes.modes, radius_m=modes.radius_m,
                        shapes=modes.shapes, nodes=modes.nodes, source=str(target))
    return modes


#: Thesis table 2-3, free-free CRH380A wheelset, one row per *mode number*: (frequency Hz,
#: nodal diameter, label).  The thesis prints travelling pairs as ``f(2,3)``, so a pair is
#: two rows here — ``_pairs`` needs both to build the antisymmetric block.  ``f(31)`` is
#: described in the text but truncated in the table, so its 1900 Hz is approximate; it only
#: sets the mode count that a 2 kHz cutoff should find (31, matching SDITT's commented
#: ``NM_FW = 31*1``), and nothing else in this module depends on it.
TABLE_2_3: tuple[tuple[float, int, str], ...] = (
    (90.0, 0, "torsion"),
    (108.0, 1, "first bending"),
    (108.0, 1, "first bending"),
    (190.1, 1, "in-phase wheel deflection"),
    (190.1, 1, "in-phase wheel deflection"),
    (320.5, 0, "first symmetric umbrella"),
    (360.8, 1, "anti-phase wheel deflection"),
    (360.8, 1, "anti-phase wheel deflection"),
    (459.7, 2, "two nodal diameters"),
    (459.7, 2, "two nodal diameters"),
    (459.7, 2, "two nodal diameters"),
    (459.7, 2, "two nodal diameters"),
    (485.2, 0, "first anti-symmetric umbrella"),
    (676.5, 1, "second bending"),
    (676.5, 1, "second bending"),
    (909.3, 1, "third bending"),
    (909.3, 1, "third bending"),
    (1066.3, 0, "second symmetric umbrella"),
    (1174.0, 0, "axle bending"),
    (1185.9, 1, "fourth bending"),
    (1185.9, 1, "fourth bending"),
    (1204.3, 3, "three nodal diameters"),
    (1204.3, 3, "three nodal diameters"),
    (1204.3, 3, "three nodal diameters"),
    (1204.3, 3, "three nodal diameters"),
    (1614.1, 1, "fifth bending"),
    (1614.1, 1, "fifth bending"),
    (1852.7, 0, "second anti-symmetric umbrella"),
    (1872.2, 1, "sixth bending"),
    (1872.2, 1, "sixth bending"),
    (1900.0, 0, "third symmetric umbrella"),
)


def thesis_crh380a_modes(*, radius_m: float = 0.43, cutoff_hz: float = 2000.0) -> ModeSet:
    """The published table 2-3 as a ``ModeSet``, with the thesis's own damping rule.

    The thesis prints frequencies only; the damping ratios come from SDITT's
    ``DR_FW``: ``1e-3`` for axisymmetric modes, ``1e-4`` from two nodal diameters up, and
    ``1e-2`` for the single-nodal-diameter modes.  This is the B path — a real modal set
    replaces this function and nothing downstream changes.
    """

    modes = tuple(
        Mode(
            index=position + 1,
            frequency_hz=frequency,
            damping_ratio=_thesis_damping_ratio(diameter),
            nodal_diameter=diameter,
            label=label,
        )
        for position, (frequency, diameter, label) in enumerate(TABLE_2_3)
    )
    return ModeSet(modes=modes, radius_m=radius_m, source="thesis table 2-3").cut(cutoff_hz)


def _thesis_damping_ratio(nodal_diameter: int) -> float:
    if nodal_diameter == 0:
        return 1.0e-3
    if nodal_diameter == 1:
        return 1.0e-2
    return 1.0e-4


def mode_table(modes: ModeSet) -> list[dict[str, Any]]:
    """Rows for a report or a CLI listing."""

    pairs: dict[int, int] = {}
    for left, right, _diameter in modes._pairs():
        # Both halves of a travelling pair report the other, otherwise a listing shows the
        # same mode once as paired and once as unpaired depending on where it sat in the table.
        pairs[left] = right
        pairs[right] = left
    rows: list[dict[str, Any]] = []
    for position, item in enumerate(modes.modes):
        partner = pairs.get(position)
        rows.append({
            "index": item.index,
            "frequency_hz": item.frequency_hz,
            "nodal_diameter": item.nodal_diameter,
            "damping_ratio": item.damping_ratio,
            "pair": None if partner is None else partner,
            "label": item.label,
        })
    return rows


def assert_split_matches_thesis(
    modes: ModeSet, *, speed_kmh: float = 200.0, tolerance_hz: float = 3.5
) -> list[dict[str, Any]]:
    """Compare the predicted split against the thesis's measured 420.2 / 499.1 / …

    Kept in the library, not only in a test, because the whole flexible-wheelset layer is
    credible only while this holds: it is the one check that needs no mode shapes and no
    ANSYS, and it goes red the moment the gyroscopic term is assembled wrongly.

    The tolerance is 3.5 Hz, not 1 Hz, because ``C`` here is only ``G·G``: omitting ``J``
    and ``E`` (2-33…2-36) leaves a residual that grows with nodal diameter — 1.6 Hz at ND2
    and 2.8–3.0 Hz at ND3.  Reporting the measured numbers next to the predicted ones keeps
    that visible instead of hiding it inside a loose comparison.
    """

    speed_m_s = speed_kmh / 3.6
    spin = modes.rotational_speed(speed_m_s)
    measured = {(2, 459.7): (420.2, 499.1), (3, 1204.3): (1145.4, 1263.0)}
    rows: list[dict[str, Any]] = []
    for diameter, base, backward, forward in modes.pair_splits_hz(spin):
        reference = measured.get((diameter, round(base, 1)))
        rows.append({
            "nodal_diameter": diameter,
            "base_hz": base,
            "backward_hz": backward,
            "forward_hz": forward,
            "measured": reference,
            "error_hz": None if reference is None else max(
                abs(backward - reference[0]), abs(forward - reference[1])
            ),
        })
    for row in rows:
        error = row["error_hz"]
        if error is None or error <= tolerance_hz:
            continue
        reference = row["measured"]
        raise ModeError(
            f"ND{row['nodal_diameter']} at {row['base_hz']} Hz splits to "
            f"{row['backward_hz']:.1f} / {row['forward_hz']:.1f} Hz, but the thesis "
            f"measured {reference[0]} / {reference[1]} Hz "
            f"(error {error:.1f} Hz > {tolerance_hz:g} Hz)"
        )
    return rows
