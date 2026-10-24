"""Typed history tables: the schema behind ``history.csv``.

The solver's writer stays byte-for-byte unchanged (frozen-oracle reproducibility),
but readers must not guess: ``metrics`` used to parse column names by string, which
turned the on-disk naming into an implicit public contract. This module makes the
contract explicit — every column carries a unit and a kind — so that observation
operators (simulation-to-simulation *and* measured) can select channels by meaning
instead of by string slicing.

Schema ``velch-history-v1`` is the current run format: one header row of channel
names, one row per output sample, SI units, all values finite.

**Naming trap** (documented here because it is the one place the schema is ambiguous):
vehicle degrees of freedom are ``axle<k>_y_m / axle<k>_z_m`` (the wheelset), while the
*track* degrees of freedom of a compliant rail reuse the pattern
``axle<k>_<left|right>_y_m / axle<k>_<left|right>_z_m`` — those two columns are the rail's own
lateral and vertical displacement, i.e. the simulated counterpart of a measured rail
displacement channel. Reading ``axle1_right_z_m`` as "the right wheel of axle 1" is the
single easiest mistake to make in this schema.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Mapping

import numpy as np

HISTORY_SCHEMA = "velch-history-v1"

Kind = Literal["time", "state", "velocity", "acceleration", "force", "moment", "contact", "flag"]


class HistoryError(ValueError):
    """Raised when a history file cannot be read as a history table."""


@dataclass(frozen=True)
class Channel:
    """One column: its name, SI unit and semantic kind."""

    name: str
    unit: str
    kind: Kind

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "unit": self.unit, "kind": self.kind}


_FORCES = ("_normal_n", "_fx_n", "_fy_n", "_fz_n")


def classify(name: str) -> Channel:
    """Derive unit and kind from a channel name.

    The rules mirror the writer in :mod:`velch.vehicle_solver`; a name that matches
    no rule raises rather than silently defaulting, because a mistyped channel in an
    observation operator would otherwise compare metres with newtons.
    """

    if name == "time_s":
        return Channel(name, "s", "time")
    if name.endswith("_m_per_s"):
        return Channel(name, "m/s", "velocity")
    if name.endswith("_rad_per_s"):
        return Channel(name, "rad/s", "velocity")
    # Acceleration channels carry their own units: ``axle1_y_acc_m_per_s2`` would otherwise fall
    # through to no rule at all and abort the read of a file the writer had just produced.
    if name.endswith("_acc_m_per_s2"):
        return Channel(name, "m/s^2", "acceleration")
    if name.endswith("_acc_rad_per_s2"):
        return Channel(name, "rad/s^2", "acceleration")
    if name.endswith("_nm"):
        return Channel(name, "N*m", "moment")
    if name.endswith(_FORCES):
        return Channel(name, "N", "force")
    if name.endswith("_penetration_m"):
        return Channel(name, "m", "contact")
    if name.endswith("_active"):
        return Channel(name, "-", "flag")
    if name.endswith("_rad"):
        return Channel(name, "rad", "state")
    if name.endswith("_m"):
        return Channel(name, "m", "state")
    raise HistoryError(f"cannot classify history channel {name!r}")


@dataclass(frozen=True)
class HistoryTable:
    """A run's channel data, typed and finite-checked."""

    schema_version: str
    time_s: np.ndarray
    channels: Mapping[str, Channel]
    data: np.ndarray
    source: str
    ordering: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.data.ndim != 2:
            raise HistoryError("history data must be (n_channel, n_time)")
        if self.data.shape[1] != self.time_s.shape[0]:
            raise HistoryError("history data and time length disagree")
        if self.data.shape[0] != len(self.ordering):
            raise HistoryError("history channel count disagrees with the ordering")

    def __getitem__(self, name: str) -> np.ndarray:
        try:
            index = self.ordering.index(name)
        except ValueError as exc:
            raise HistoryError(f"unknown channel {name!r}; have {len(self.ordering)}") from exc
        return self.data[index]

    def __contains__(self, name: object) -> bool:
        return name in self.ordering

    def select(self, names: Iterable[str]) -> "HistoryTable":
        wanted = tuple(names)
        missing = [n for n in wanted if n not in self]
        if missing:
            raise HistoryError(f"unknown channels: {', '.join(missing)}")
        indices = [self.ordering.index(n) for n in wanted]
        return HistoryTable(self.schema_version, self.time_s,
                            {n: self.channels[n] for n in wanted},
                            self.data[indices], self.source, wanted)

    def where(self, predicate) -> "HistoryTable":
        names = [n for n in self.ordering if predicate(self.channels[n])]
        return self.select(names)

    @property
    def samples(self) -> int:
        return int(self.time_s.shape[0])


def read_history(path: str | Path) -> HistoryTable:
    """Read ``history.csv`` (or any file with the same layout) into a typed table."""

    source = Path(path)
    if source.suffix.lower() != ".csv":
        source = source / "history.csv"
    if not source.is_file():
        raise HistoryError(f"history not found: {source}")
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as exc:  # pragma: no cover - empty file
            raise HistoryError(f"empty history: {source}") from exc
        rows = list(reader)
    if not rows:
        raise HistoryError(f"history has no samples: {source}")
    if "time_s" not in header:
        raise HistoryError(f"history has no time_s column: {source}")
    try:
        matrix = np.array([[float(value) for value in row] for row in rows], dtype=float)
    except ValueError as exc:
        raise HistoryError(f"non-numeric sample in {source.name}") from exc
    if matrix.shape[1] != len(header):
        raise HistoryError(f"ragged history: {source.name}")
    if not np.all(np.isfinite(matrix)):
        raise HistoryError(f"non-finite sample in {source.name}")
    channels = {name: classify(name) for name in header}
    time_index = header.index("time_s")
    return HistoryTable(HISTORY_SCHEMA, matrix[:, time_index], channels,
                        matrix.T, str(source), tuple(header))


def write_history(path: str | Path, table: HistoryTable) -> Path:
    """Write a typed table as CSV.

    The run writer in :mod:`velch.vehicle_solver` keeps its own byte-exact output for
    oracle reproducibility; this writer exists for derived/synthetic tables.
    """

    target = Path(path)
    if target.suffix.lower() != ".csv":
        target = target / "history.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(list(table.ordering))
        for index in range(table.samples):
            writer.writerow([f"{value:.17g}" for value in table.data[:, index]])
    return target


_ACCELERATION_SUFFIX = {"x_m": "x_acc_m_per_s2", "y_m": "y_acc_m_per_s2",
                        "z_m": "z_acc_m_per_s2", "roll_rad": "roll_acc_rad_per_s2",
                        "pitch_rad": "pitch_acc_rad_per_s2", "yaw_rad": "yaw_acc_rad_per_s2"}


def channel_names(kind: Kind | None = None) -> tuple[str, ...]:
    """The registry of channel names this build can emit (by kind).

    The body layout listed here is the four-axle five-coordinate one (``axle1``…``axle4``,
    ``bogie1``…``bogie2``, ``carbody``) plus its accelerations — the path every frozen oracle run
    takes.  A node-table vehicle (``"layout": "v2-node"``) additionally emits the longitudinal
    coordinate and, with axle boxes, ``axle<k>_box_<left|right>_*``; :func:`classify` accepts all of
    them, so a reader may take its channel list from the file's own header instead of this table.
    """

    sides = ("left", "right")
    names: list[str] = ["time_s"]
    for axle in range(1, 5):
        names.append(f"axle{axle}_x_m")
    for axle in range(1, 5):
        for axis in ("y", "z"):
            names.append(f"axle{axle}_{axis}_m")
        for axis in ("roll", "spin", "yaw"):
            names.append(f"axle{axle}_{axis}_rad")
    for bogie in range(1, 3):
        names.extend([f"bogie{bogie}_y_m", f"bogie{bogie}_z_m",
                      f"bogie{bogie}_roll_rad", f"bogie{bogie}_pitch_rad",
                      f"bogie{bogie}_yaw_rad"])
    names.extend(["carbody_y_m", "carbody_z_m", "carbody_roll_rad",
                  "carbody_pitch_rad", "carbody_yaw_rad"])
    for name in tuple(names):
        for suffix, acceleration in _ACCELERATION_SUFFIX.items():
            if name.endswith("_" + suffix):
                names.append(f"{name[: -len(suffix)]}{acceleration}")
                break
    for axle in range(1, 5):
        for side in sides:
            names.extend([f"axle{axle}_{side}_normal_n", f"axle{axle}_{side}_fx_n",
                          f"axle{axle}_{side}_fy_n", f"axle{axle}_{side}_fz_n",
                          f"axle{axle}_{side}_penetration_m",
                          f"axle{axle}_{side}_active"])
    classified = tuple(name for name in names if kind is None or classify(name).kind == kind)
    return classified
